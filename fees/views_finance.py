from __future__ import annotations

from django.http import HttpResponse
from django.db import transaction
from django.utils import timezone
from drf_spectacular.utils import OpenApiResponse, extend_schema
from rest_framework import mixins, status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.views import APIView

from academics.models import StudentEnrollments
from common.pagination import MetaPageNumberPagination
from common.permissions import IsAuthenticatedAndActive
from fees.models import (
    ConcessionStatus,
    FeeAdvanceCredit,
    FeeConfiguration,
    FeeInvoice,
    FeePayment,
    StudentFeeConcession,
)
from fees.pdfs import build_bulk_invoice_pdf, build_invoice_pdf, build_payment_receipt_pdf
from fees.permissions import (
    CanManageFeeConcessions,
    CanPostFeePayments,
    CanReverseFinancialDocuments,
    CanViewFeeManagement,
)
from fees.serializers_finance import (
    BulkInvoiceGenerateSerializer,
    FeeAdvanceCreditReadSerializer,
    FeeConfigurationSerializer,
    FeeInvoiceReadSerializer,
    FeePaymentCreateSerializer,
    FeePaymentReadSerializer,
    FinancialReasonSerializer,
    InvoiceGenerateSerializer,
    InvoiceIdListSerializer,
    StudentFeeConcessionSerializer,
    StudentFeeWalletSerializer,
)
from fees.services.audit import audit
from fees.services.configuration import get_fee_configuration
from fees.services.invoice_correction_service import void_invoice
from fees.services.invoice_service import bulk_generate_invoices, generate_invoice
from fees.services.payment_service import post_payment, reverse_payment
from fees.services.wallet_service import rebuild_wallet
from utils.get_school_id_by_token import get_school_for_user


def _pdf_response(content: bytes, filename: str):
    response = HttpResponse(content, content_type="application/pdf")
    response["Content-Disposition"] = f'attachment; filename="{filename}"'
    response["Content-Length"] = str(len(content))
    response["X-Content-Type-Options"] = "nosniff"
    return response


class FeeInvoiceViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = FeeInvoiceReadSerializer
    pagination_class = MetaPageNumberPagination
    search_fields = [
        "invoice_number", "student__first_name", "student__middle_name", "student__last_name",
        "student__registration_no", "student__phone",
    ]
    ordering_fields = ["invoice_date", "due_date", "period_start", "created_at", "due_amount", "total_amount"]
    ordering = ["-created_at"]

    def get_permissions(self):
        if self.action in ["generate", "bulk_generate", "bulk_generate_pdf"]:
            return [IsAuthenticatedAndActive(), CanPostFeePayments()]
        if self.action == "void":
            return [IsAuthenticatedAndActive(), CanReverseFinancialDocuments()]
        return [IsAuthenticatedAndActive(), CanViewFeeManagement()]

    def get_queryset(self):
        school = get_school_for_user(self.request.user)
        qs = FeeInvoice.objects.select_related(
            "school", "student", "batch", "academic_class", "enrollment", "generated_by", "voided_by"
        ).prefetch_related("lines__adjustments").filter(school=school)
        params = self.request.query_params
        if params.get("student_id"):
            qs = qs.filter(student_id=params["student_id"])
        if params.get("enrollment_id"):
            qs = qs.filter(enrollment_id=params["enrollment_id"])
        if params.get("batch_id"):
            qs = qs.filter(batch_id=params["batch_id"])
        if params.get("academic_class_id"):
            qs = qs.filter(academic_class_id=params["academic_class_id"])
        if params.get("status"):
            qs = qs.filter(status=params["status"])
        if params.get("from_date"):
            qs = qs.filter(period_end__gte=params["from_date"])
        if params.get("to_date"):
            qs = qs.filter(period_start__lte=params["to_date"])
        return qs

    @extend_schema(request=InvoiceGenerateSerializer, responses={201: FeeInvoiceReadSerializer})
    @action(detail=False, methods=["post"], url_path="generate")
    def generate(self, request):
        serializer = InvoiceGenerateSerializer(data=request.data, context={"request": request})
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        invoice, created = generate_invoice(
            school=get_school_for_user(request.user),
            enrollment=data["enrollment"],
            period_start=data["period_start"],
            period_end=data["period_end"],
            actor=request.user,
            invoice_date=data.get("invoice_date"),
            due_date=data.get("due_date"),
            apply_advance=data.get("apply_advance"),
            notes=data.get("notes", ""),
            idempotency_key=data.get("idempotency_key"),
        )
        return Response(
            {
                "message": "Fee invoice generated." if created else "Existing invoice returned; no duplicate was created.",
                "created": created,
                "data": FeeInvoiceReadSerializer(invoice).data,
            },
            status=status.HTTP_201_CREATED if created else status.HTTP_200_OK,
        )

    @extend_schema(request=BulkInvoiceGenerateSerializer, responses={201: FeeInvoiceReadSerializer(many=True)})
    @action(detail=False, methods=["post"], url_path="bulk-generate")
    def bulk_generate(self, request):
        serializer = BulkInvoiceGenerateSerializer(data=request.data, context={"request": request})
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        results = bulk_generate_invoices(
            school=get_school_for_user(request.user),
            actor=request.user,
            period_start=data["period_start"],
            period_end=data["period_end"],
            student_ids=data.get("student_ids"),
            enrollment_ids=data.get("enrollment_ids"),
            batch_id=data.get("batch_id"),
            academic_class_id=data.get("academic_class_id"),
            invoice_date=data.get("invoice_date"),
            due_date=data.get("due_date"),
            apply_advance=data.get("apply_advance"),
            notes=data.get("notes", ""),
        )
        invoices = [invoice for invoice, _ in results]
        return Response(
            {
                "message": "Bulk fee invoices processed.",
                "created_count": sum(1 for _, created in results if created),
                "existing_count": sum(1 for _, created in results if not created),
                "data": FeeInvoiceReadSerializer(invoices, many=True).data,
            },
            status=status.HTTP_201_CREATED,
        )

    @extend_schema(request=BulkInvoiceGenerateSerializer, responses={200: OpenApiResponse(description="Combined PDF")})
    @action(detail=False, methods=["post"], url_path="bulk-generate-pdf")
    def bulk_generate_pdf(self, request):
        serializer = BulkInvoiceGenerateSerializer(data=request.data, context={"request": request})
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        results = bulk_generate_invoices(
            school=get_school_for_user(request.user),
            actor=request.user,
            period_start=data["period_start"],
            period_end=data["period_end"],
            student_ids=data.get("student_ids"),
            enrollment_ids=data.get("enrollment_ids"),
            batch_id=data.get("batch_id"),
            academic_class_id=data.get("academic_class_id"),
            invoice_date=data.get("invoice_date"),
            due_date=data.get("due_date"),
            apply_advance=data.get("apply_advance"),
            notes=data.get("notes", ""),
        )
        invoices = [invoice for invoice, _ in results]
        filename = f"fee-invoices-{data['period_start']}-to-{data['period_end']}.pdf"
        return _pdf_response(build_bulk_invoice_pdf(invoices), filename)

    @extend_schema(request=InvoiceIdListSerializer, responses={200: OpenApiResponse(description="Combined PDF")})
    @action(detail=False, methods=["post"], url_path="bulk-pdf")
    def bulk_pdf(self, request):
        serializer = InvoiceIdListSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        requested_ids = serializer.validated_data["invoice_ids"]
        invoices = list(self.get_queryset().filter(id__in=requested_ids).order_by("student__first_name", "period_start"))
        if len(invoices) != len(set(requested_ids)):
            return Response({"invoice_ids": ["One or more invoices were not found in your school."]}, status=400)
        return _pdf_response(build_bulk_invoice_pdf(invoices), "selected-fee-invoices.pdf")

    @extend_schema(responses={200: OpenApiResponse(description="Invoice PDF")})
    @action(detail=True, methods=["get"], url_path="pdf")
    def pdf(self, request, pk=None):
        invoice = self.get_object()
        return _pdf_response(build_invoice_pdf(invoice), f"{invoice.invoice_number}.pdf")

    @extend_schema(request=FinancialReasonSerializer, responses={200: FeeInvoiceReadSerializer})
    @action(detail=True, methods=["post"], url_path="void")
    def void(self, request, pk=None):
        serializer = FinancialReasonSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        invoice, changed = void_invoice(
            school=get_school_for_user(request.user),
            invoice=self.get_object(),
            actor=request.user,
            reason=serializer.validated_data["reason"],
        )
        return Response({
            "message": "Invoice voided." if changed else "Invoice was already void.",
            "data": FeeInvoiceReadSerializer(invoice).data,
        })


class FeePaymentViewSet(
    mixins.CreateModelMixin,
    mixins.ListModelMixin,
    mixins.RetrieveModelMixin,
    viewsets.GenericViewSet,
):
    pagination_class = MetaPageNumberPagination
    search_fields = [
        "receipt_number", "external_reference", "student__first_name", "student__last_name",
        "student__registration_no", "student__phone",
    ]
    ordering_fields = ["paid_at", "amount", "created_at"]
    ordering = ["-paid_at", "-created_at"]

    def get_permissions(self):
        if self.action == "create":
            return [IsAuthenticatedAndActive(), CanPostFeePayments()]
        if self.action == "reverse":
            return [IsAuthenticatedAndActive(), CanReverseFinancialDocuments()]
        return [IsAuthenticatedAndActive(), CanViewFeeManagement()]

    def get_serializer_class(self):
        return FeePaymentCreateSerializer if self.action == "create" else FeePaymentReadSerializer

    def get_queryset(self):
        school = get_school_for_user(self.request.user)
        qs = FeePayment.objects.select_related(
            "school", "student", "batch", "academic_class", "enrollment", "received_by"
        ).prefetch_related("allocations__invoice").filter(school=school)
        params = self.request.query_params
        if params.get("student_id"):
            qs = qs.filter(student_id=params["student_id"])
        if params.get("enrollment_id"):
            qs = qs.filter(enrollment_id=params["enrollment_id"])
        if params.get("status"):
            qs = qs.filter(status=params["status"])
        if params.get("from_date"):
            qs = qs.filter(paid_at__date__gte=params["from_date"])
        if params.get("to_date"):
            qs = qs.filter(paid_at__date__lte=params["to_date"])
        return qs

    @extend_schema(request=FeePaymentCreateSerializer, responses={201: FeePaymentReadSerializer})
    def create(self, request, *args, **kwargs):
        serializer = FeePaymentCreateSerializer(data=request.data, context={"request": request})
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        payment, created = post_payment(
            school=get_school_for_user(request.user),
            enrollment=data["enrollment"],
            actor=request.user,
            amount=data["amount"],
            paid_at=data["paid_at"],
            payment_method=data["payment_method"],
            idempotency_key=data["idempotency_key"],
            invoice_ids=data.get("invoice_ids"),
            auto_allocate=data.get("auto_allocate", True),
            external_reference=data.get("external_reference", ""),
            notes=data.get("notes", ""),
        )
        return Response(
            {
                "message": "Payment posted." if created else "Existing payment returned; no duplicate was posted.",
                "created": created,
                "data": FeePaymentReadSerializer(payment).data,
            },
            status=status.HTTP_201_CREATED if created else status.HTTP_200_OK,
        )

    @extend_schema(responses={200: OpenApiResponse(description="Payment receipt PDF")})
    @action(detail=True, methods=["get"], url_path="receipt-pdf")
    def receipt_pdf(self, request, pk=None):
        payment = self.get_object()
        return _pdf_response(build_payment_receipt_pdf(payment), f"{payment.receipt_number}.pdf")

    @extend_schema(request=FinancialReasonSerializer, responses={200: FeePaymentReadSerializer})
    @action(detail=True, methods=["post"], url_path="reverse")
    def reverse(self, request, pk=None):
        serializer = FinancialReasonSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        payment, changed = reverse_payment(
            school=get_school_for_user(request.user),
            payment=self.get_object(),
            actor=request.user,
            reason=serializer.validated_data["reason"],
        )
        return Response({
            "message": "Payment reversed." if changed else "Payment was already reversed.",
            "data": FeePaymentReadSerializer(payment).data,
        })


class StudentFeeConcessionViewSet(
    mixins.CreateModelMixin,
    mixins.ListModelMixin,
    mixins.RetrieveModelMixin,
    mixins.UpdateModelMixin,
    viewsets.GenericViewSet,
):
    serializer_class = StudentFeeConcessionSerializer
    pagination_class = MetaPageNumberPagination
    ordering = ["-created_at"]

    def get_permissions(self):
        if self.action in ["create", "update", "partial_update", "revoke"]:
            return [IsAuthenticatedAndActive(), CanManageFeeConcessions()]
        return [IsAuthenticatedAndActive(), CanViewFeeManagement()]

    def get_queryset(self):
        school = get_school_for_user(self.request.user)
        qs = StudentFeeConcession.objects.select_related(
            "student", "batch", "academic_class", "fee_head", "approved_by", "revoked_by"
        ).filter(school=school)
        params = self.request.query_params
        if params.get("student_id"):
            qs = qs.filter(student_id=params["student_id"])
        if params.get("status"):
            qs = qs.filter(status=params["status"])
        return qs

    def perform_create(self, serializer):
        concession = serializer.save()
        audit(
            school=concession.school, actor=self.request.user, event_type="CONCESSION_CREATED",
            entity=concession, payload={"kind": concession.kind, "value": str(concession.value), "reason": concession.reason},
        )

    def perform_update(self, serializer):
        concession = serializer.save()
        audit(
            school=concession.school, actor=self.request.user, event_type="CONCESSION_UPDATED",
            entity=concession, payload={"kind": concession.kind, "value": str(concession.value), "reason": concession.reason},
        )

    @extend_schema(request=FinancialReasonSerializer, responses={200: StudentFeeConcessionSerializer})
    @action(detail=True, methods=["post"], url_path="revoke")
    def revoke(self, request, pk=None):
        serializer = FinancialReasonSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        concession = self.get_object()
        if concession.status == ConcessionStatus.REVOKED:
            return Response({"message": "Concession was already revoked.", "data": self.get_serializer(concession).data})
        concession.status = ConcessionStatus.REVOKED
        concession.revoked_by = request.user
        concession.revoked_at = timezone.now()
        concession.revoke_reason = serializer.validated_data["reason"]
        concession.save(update_fields=["status", "revoked_by", "revoked_at", "revoke_reason", "updated_at"])
        audit(
            school=concession.school, actor=request.user, event_type="CONCESSION_REVOKED",
            entity=concession, payload={"reason": concession.revoke_reason},
        )
        return Response({"message": "Concession revoked.", "data": self.get_serializer(concession).data})


class FeeAdvanceCreditViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = FeeAdvanceCreditReadSerializer
    pagination_class = MetaPageNumberPagination
    permission_classes = [IsAuthenticatedAndActive, CanViewFeeManagement]
    ordering = ["-created_at"]

    def get_queryset(self):
        school = get_school_for_user(self.request.user)
        qs = FeeAdvanceCredit.objects.select_related(
            "student", "enrollment", "payment"
        ).prefetch_related("applications__invoice").filter(school=school)
        params = self.request.query_params
        if params.get("student_id"):
            qs = qs.filter(student_id=params["student_id"])
        if params.get("enrollment_id"):
            qs = qs.filter(enrollment_id=params["enrollment_id"])
        if params.get("status"):
            qs = qs.filter(status=params["status"])
        return qs


class FeeConfigurationAPIView(APIView):
    permission_classes = [IsAuthenticatedAndActive, CanManageFeeConcessions]

    def get(self, request):
        school = get_school_for_user(request.user)
        config = get_fee_configuration(school)
        return Response({"data": FeeConfigurationSerializer(config).data})

    def patch(self, request):
        school = get_school_for_user(request.user)
        with transaction.atomic():
            config = get_fee_configuration(school)
            before = FeeConfigurationSerializer(config).data
            serializer = FeeConfigurationSerializer(config, data=request.data, partial=True)
            serializer.is_valid(raise_exception=True)
            old_currency = config.currency
            config = serializer.save()
            if config.currency != old_currency:
                from fees.models import FeeStructure
                FeeStructure.objects.filter(school=school).update(currency=config.currency)
            audit(
                school=school, actor=request.user, event_type="FEE_CONFIGURATION_UPDATED",
                entity=config, payload={"before": before, "after": serializer.data},
            )
        return Response({"message": "Fee configuration updated.", "data": serializer.data})


class StudentFeeAccountAPIView(APIView):
    permission_classes = [IsAuthenticatedAndActive, CanViewFeeManagement]

    def get(self, request, enrollment_id):
        school = get_school_for_user(request.user)
        enrollment = StudentEnrollments.objects.select_related(
            "student", "batch__school", "academic_class"
        ).filter(id=enrollment_id, batch__school=school).first()
        if not enrollment:
            return Response({"enrollment_id": ["Enrollment not found in your school."]}, status=404)
        wallet = rebuild_wallet(enrollment=enrollment)
        invoices = FeeInvoice.objects.filter(enrollment=enrollment).order_by("-invoice_date", "-created_at")[:20]
        payments = FeePayment.objects.filter(enrollment=enrollment).order_by("-paid_at", "-created_at")[:20]
        advances = FeeAdvanceCredit.objects.select_related("payment").prefetch_related(
            "applications__invoice"
        ).filter(enrollment=enrollment).order_by("-created_at")[:20]
        return Response({
            "wallet": StudentFeeWalletSerializer(wallet).data,
            "recent_invoices": FeeInvoiceReadSerializer(invoices, many=True).data,
            "recent_payments": FeePaymentReadSerializer(payments, many=True).data,
            "advance_credits": FeeAdvanceCreditReadSerializer(advances, many=True).data,
        })
