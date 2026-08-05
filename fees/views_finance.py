from __future__ import annotations

from django.db import transaction
from django.http import HttpResponse
from django.utils import timezone
from drf_spectacular.utils import OpenApiResponse, extend_schema
from rest_framework import mixins, status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.exceptions import ValidationError

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
from fees.pdfs import (
    build_bulk_invoice_pdf,
    build_invoice_pdf,
    build_payment_receipt_pdf,
)
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
from fees.services.invoice_service import (
    bulk_generate_invoices,
    generate_invoice,
)
from fees.services.payment_service import (
    post_payment,
    reverse_payment,
)
from fees.services.wallet_service import rebuild_wallet
from utils.get_school_id_by_token import get_school_for_user


def _pdf_response(content: bytes, filename: str) -> HttpResponse:
    response = HttpResponse(
        content,
        content_type="application/pdf",
    )
    response["Content-Disposition"] = (
        f'attachment; filename="{filename}"'
    )
    response["Content-Length"] = str(len(content))
    response["X-Content-Type-Options"] = "nosniff"

    return response


class FeeInvoiceViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = FeeInvoiceReadSerializer
    pagination_class = MetaPageNumberPagination

    search_fields = [
        "invoice_number",
        "student__first_name",
        "student__middle_name",
        "student__last_name",
        "student__registration_no",
        "student__phone",
    ]

    ordering_fields = [
        "invoice_date",
        "due_date",
        "period_start",
        "created_at",
        "due_amount",
        "total_amount",
    ]

    ordering = ["-created_at"]

    def get_permissions(self):
        if self.action in [
            "generate",
            "bulk_generate",
            "bulk_generate_pdf",
        ]:
            return [
                IsAuthenticatedAndActive(),
                CanPostFeePayments(),
            ]

        if self.action == "void":
            return [
                IsAuthenticatedAndActive(),
                CanReverseFinancialDocuments(),
            ]

        return [
            IsAuthenticatedAndActive(),
            CanViewFeeManagement(),
        ]

    def get_queryset(self):
        school = get_school_for_user(
            self.request.user
        )

        queryset = (
            FeeInvoice.objects
            .select_related(
                "school",
                "student",
                "batch",
                "academic_class",
                "enrollment",
                "enrollment__section",
                "generated_by",
                "voided_by",
            )
            .prefetch_related(
                "lines__adjustments"
            )
            .filter(
                school=school
            )
        )

        params = self.request.query_params

        student_id = params.get("student_id")
        enrollment_id = params.get("enrollment_id")
        batch_id = params.get("batch_id")
        academic_class_id = params.get(
            "academic_class_id"
        )
        section_id = params.get("section_id")
        invoice_status = params.get("status")
        from_date = params.get("from_date")
        to_date = params.get("to_date")

        if student_id:
            queryset = queryset.filter(
                student_id=student_id
            )

        if enrollment_id:
            queryset = queryset.filter(
                enrollment_id=enrollment_id
            )

        if batch_id:
            queryset = queryset.filter(
                batch_id=batch_id
            )

        if academic_class_id:
            queryset = queryset.filter(
                academic_class_id=academic_class_id
            )

        if section_id:
            queryset = queryset.filter(
                enrollment__section_id=section_id
            )

        if invoice_status:
            queryset = queryset.filter(
                status=invoice_status
            )

        if from_date:
            queryset = queryset.filter(
                period_end__gte=from_date
            )

        if to_date:
            queryset = queryset.filter(
                period_start__lte=to_date
            )

        return queryset

    @extend_schema(
        request=InvoiceGenerateSerializer,
        responses={
            200: FeeInvoiceReadSerializer,
            201: FeeInvoiceReadSerializer,
        },
    )
    @action(
        detail=False,
        methods=["post"],
        url_path="generate",
    )
    def generate(self, request):
        serializer = InvoiceGenerateSerializer(
            data=request.data,
            context={"request": request},
        )
        serializer.is_valid(
            raise_exception=True
        )

        data = serializer.validated_data

        invoice, created = generate_invoice(
            school=get_school_for_user(
                request.user
            ),
            enrollment=data["enrollment"],
            period_start=data["period_start"],
            period_end=data["period_end"],
            actor=request.user,
            invoice_date=data.get(
                "invoice_date"
            ),
            due_date=data.get(
                "due_date"
            ),
            apply_advance=data.get(
                "apply_advance"
            ),
            notes=data.get(
                "notes",
                "",
            ),
            idempotency_key=data.get(
                "idempotency_key"
            ),
        )

        response_status = (
            status.HTTP_201_CREATED
            if created
            else status.HTTP_200_OK
        )

        return Response(
            {
                "message": (
                    "Fee invoice generated."
                    if created
                    else (
                        "Existing invoice returned; "
                        "no duplicate was created."
                    )
                ),
                "created": created,
                "data": FeeInvoiceReadSerializer(
                    invoice
                ).data,
            },
            status=response_status,
        )

    @extend_schema(
        request=BulkInvoiceGenerateSerializer,
        responses={
            200: OpenApiResponse(
                description=(
                    "Bulk invoice generation completed "
                    "without creating new invoices."
                )
            ),
            201: OpenApiResponse(
                description=(
                    "Bulk invoice generation completed "
                    "and created one or more invoices."
                )
            ),
        },
    )
    @action(
        detail=False,
        methods=["post"],
        url_path="bulk-generate",
    )
    def bulk_generate(self, request):
        serializer = BulkInvoiceGenerateSerializer(
            data=request.data,
            context={"request": request},
        )
        serializer.is_valid(
            raise_exception=True
        )

        data = serializer.validated_data
        school = get_school_for_user(
            request.user
        )

        results = bulk_generate_invoices(
            school=school,
            actor=request.user,
            period_start=data["period_start"],
            period_end=data["period_end"],
            student_ids=data.get(
                "student_ids"
            ),
            enrollment_ids=data.get(
                "enrollment_ids"
            ),
            batch_id=data.get(
                "batch_id"
            ),
            academic_class_id=data.get(
                "academic_class_id"
            ),
            section_id=data.get(
                "section_id"
            ),
            invoice_date=data.get(
                "invoice_date"
            ),
            due_date=data.get(
                "due_date"
            ),
            apply_advance=data.get(
                "apply_advance"
            ),
            notes=data.get(
                "notes",
                "",
            ),
        )

        created_count = sum(
            1
            for result in results
            if result["created"]
        )

        existing_count = sum(
            1
            for result in results
            if (
                result["invoice"] is not None
                and not result["created"]
            )
        )

        failed_count = sum(
            1
            for result in results
            if result["error"] is not None
        )

        response_items = []

        for result in results:
            enrollment = result["enrollment"]
            invoice = result["invoice"]

            response_items.append({
                "enrollment_id": str(
                    enrollment.id
                ),
                "student_id": str(
                    enrollment.student_id
                ),
                "student_name": str(
                    enrollment.student
                ),
                "batch_id": enrollment.batch_id,
                "academic_class_id": str(
                    enrollment.academic_class_id
                ),
                "section_id": (
                    str(enrollment.section_id)
                    if enrollment.section_id
                    else None
                ),
                "created": result["created"],
                "status": (
                    "FAILED"
                    if result["error"] is not None
                    else (
                        "CREATED"
                        if result["created"]
                        else "EXISTING"
                    )
                ),
                "invoice": (
                    FeeInvoiceReadSerializer(
                        invoice
                    ).data
                    if invoice is not None
                    else None
                ),
                "error": result["error"],
            })

        if failed_count == 0:
            message = (
                "Bulk fee invoices processed successfully."
            )
        elif created_count > 0 or existing_count > 0:
            message = (
                "Bulk fee invoices processed with some errors."
            )
        else:
            message = (
                "No fee invoices could be processed."
            )

        response_status = (
            status.HTTP_201_CREATED
            if created_count > 0
            else status.HTTP_200_OK
        )

        return Response(
            {
                "message": message,
                "selection": {
                    "batch_id": data.get(
                        "batch_id"
                    ),
                    "academic_class_id": data.get(
                        "academic_class_id"
                    ),
                    "section_id": data.get(
                        "section_id"
                    ),
                },
                "period": {
                    "period_start": data[
                        "period_start"
                    ],
                    "period_end": data[
                        "period_end"
                    ],
                    "invoice_date": data.get(
                        "invoice_date"
                    ),
                    "due_date": data.get(
                        "due_date"
                    ),
                },
                "summary": {
                    "processed_count": len(
                        results
                    ),
                    "created_count": created_count,
                    "existing_count": existing_count,
                    "failed_count": failed_count,
                },
                "data": response_items,
            },
            status=response_status,
        )

    @extend_schema(
        request=BulkInvoiceGenerateSerializer,
        responses={
            200: OpenApiResponse(
                description=(
                    "Invoices generated or retrieved "
                    "and returned as a combined PDF."
                )
            ),
            400: OpenApiResponse(
                description=(
                    "No invoices were available "
                    "for PDF generation."
                )
            ),
        },
    )
    @action(
        detail=False,
        methods=["post"],
        url_path="bulk-generate-pdf",
    )
    def bulk_generate_pdf(self, request):
        serializer = BulkInvoiceGenerateSerializer(
            data=request.data,
            context={"request": request},
        )
        serializer.is_valid(
            raise_exception=True
        )

        data = serializer.validated_data
        school = get_school_for_user(
            request.user
        )

        results = bulk_generate_invoices(
            school=school,
            actor=request.user,
            period_start=data["period_start"],
            period_end=data["period_end"],
            student_ids=data.get(
                "student_ids"
            ),
            enrollment_ids=data.get(
                "enrollment_ids"
            ),
            batch_id=data.get(
                "batch_id"
            ),
            academic_class_id=data.get(
                "academic_class_id"
            ),
            section_id=data.get(
                "section_id"
            ),
            invoice_date=data.get(
                "invoice_date"
            ),
            due_date=data.get(
                "due_date"
            ),
            apply_advance=data.get(
                "apply_advance"
            ),
            notes=data.get(
                "notes",
                "",
            ),
        )

        invoices = [
            result["invoice"]
            for result in results
            if result["invoice"] is not None
        ]

        failed_count = sum(
            1
            for result in results
            if result["error"] is not None
        )

        if not invoices:
            return Response(
                {
                    "detail": (
                        "No invoices were available "
                        "for PDF generation."
                    ),
                    "summary": {
                        "processed_count": len(
                            results
                        ),
                        "invoice_count": 0,
                        "failed_count": failed_count,
                    },
                    "errors": [
                        {
                            "enrollment_id": str(
                                result["enrollment"].id
                            ),
                            "student_id": str(
                                result[
                                    "enrollment"
                                ].student_id
                            ),
                            "error": result["error"],
                        }
                        for result in results
                        if result["error"] is not None
                    ],
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        filename = (
            f"fee-invoices-"
            f"{data['period_start']}-to-"
            f"{data['period_end']}.pdf"
        )

        pdf_content = build_bulk_invoice_pdf(
            invoices
        )

        return _pdf_response(
            pdf_content,
            filename,
        )

    @extend_schema(
        request=InvoiceIdListSerializer,
        responses={
            200: OpenApiResponse(
                description=(
                    "Combined PDF for selected invoices."
                )
            ),
            400: OpenApiResponse(
                description=(
                    "One or more invoice IDs are invalid."
                )
            ),
        },
    )
    @action(
        detail=False,
        methods=["post"],
        url_path="bulk-pdf",
    )
    def bulk_pdf(self, request):
        serializer = InvoiceIdListSerializer(
            data=request.data
        )
        serializer.is_valid(
            raise_exception=True
        )

        requested_ids = (
            serializer.validated_data[
                "invoice_ids"
            ]
        )

        unique_requested_ids = set(
            requested_ids
        )

        invoices = list(
            self.get_queryset()
            .filter(
                id__in=unique_requested_ids
            )
            .order_by(
                "student__first_name",
                "student__middle_name",
                "student__last_name",
                "period_start",
            )
        )

        if len(invoices) != len(
            unique_requested_ids
        ):
            found_ids = {
                str(invoice.id)
                for invoice in invoices
            }

            missing_ids = [
                str(invoice_id)
                for invoice_id in unique_requested_ids
                if str(invoice_id) not in found_ids
            ]

            return Response(
                {
                    "invoice_ids": [
                        (
                            "One or more invoices were not "
                            "found in your school."
                        )
                    ],
                    "missing_invoice_ids": missing_ids,
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        if not invoices:
            return Response(
                {
                    "invoice_ids": [
                        "At least one invoice ID is required."
                    ]
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        return _pdf_response(
            build_bulk_invoice_pdf(
                invoices
            ),
            "selected-fee-invoices.pdf",
        )

    @extend_schema(
        responses={
            200: OpenApiResponse(
                description="Invoice PDF"
            )
        }
    )
    @action(
        detail=True,
        methods=["get"],
        url_path="pdf",
    )
    def pdf(self, request, pk=None):
        invoice = self.get_object()

        return _pdf_response(
            build_invoice_pdf(invoice),
            f"{invoice.invoice_number}.pdf",
        )

    @extend_schema(
        request=FinancialReasonSerializer,
        responses={
            200: FeeInvoiceReadSerializer
        },
    )
    @action(
        detail=True,
        methods=["post"],
        url_path="void",
    )
    def void(self, request, pk=None):
        serializer = FinancialReasonSerializer(
            data=request.data
        )
        serializer.is_valid(
            raise_exception=True
        )

        invoice, changed = void_invoice(
            school=get_school_for_user(
                request.user
            ),
            invoice=self.get_object(),
            actor=request.user,
            reason=serializer.validated_data[
                "reason"
            ],
        )

        return Response(
            {
                "message": (
                    "Invoice voided."
                    if changed
                    else "Invoice was already void."
                ),
                "data": FeeInvoiceReadSerializer(
                    invoice
                ).data,
            }
        )


class FeePaymentViewSet(
    mixins.CreateModelMixin,
    mixins.ListModelMixin,
    mixins.RetrieveModelMixin,
    viewsets.GenericViewSet,
):
    pagination_class = MetaPageNumberPagination

    search_fields = [
        "receipt_number",
        "external_reference",
        "notes",

        "student__first_name",
        "student__middle_name",
        "student__last_name",
        "student__username",
        "student__registration_no",
        "student__phone",
        "student__email",

        "batch__name",
        "academic_class__name",
        "enrollment__section__name",
    ]

    searchable_fields = search_fields
    search_param_name = "search"

    ordering_fields = [
        "receipt_number",
        "paid_at",
        "amount",
        "created_at",
        "before_payment_due",
        "after_payment_due",
    ]

    ordering_param_name = "ordering"

    ordering = [
        "-paid_at",
        "-created_at",
    ]

    sortable_fields = {
        "receipt_number": "Receipt number",
        "paid_at": "Paid at",
        "amount": "Amount",
        "created_at": "Created at",
        "before_payment_due": "Due before payment",
        "after_payment_due": "Due after payment",
    }

    filterable_fields = {
        "student_id": "Student UUID",
        "enrollment_id": "Enrollment UUID",
        "batch_id": "Batch ID",
        "academic_class_id": "Academic class UUID",
        "section_id": "Section UUID",
        "status": "Payment status",
        "payment_method": "Payment method",
        "from_date": "Paid from date",
        "to_date": "Paid to date",
    }

    def get_permissions(self):
        if self.action == "create":
            return [
                IsAuthenticatedAndActive(),
                CanPostFeePayments(),
            ]

        if self.action == "reverse":
            return [
                IsAuthenticatedAndActive(),
                CanReverseFinancialDocuments(),
            ]

        return [
            IsAuthenticatedAndActive(),
            CanViewFeeManagement(),
        ]

    def get_serializer_class(self):
        if self.action == "create":
            return FeePaymentCreateSerializer

        return FeePaymentReadSerializer

    def get_queryset(self):
        school = get_school_for_user(
            self.request.user
        )

        queryset = (
            FeePayment.objects
            .select_related(
                "school",
                "student",
                "batch",
                "academic_class",
                "enrollment",
                "enrollment__section",
                "received_by",
            )
            .prefetch_related(
                "allocations__invoice"
            )
            .filter(
                school=school
            )
        )

        params = self.request.query_params

        student_id = (
            params.get("student_id")
            or params.get("student")
            or ""
        ).strip()

        enrollment_id = (
            params.get("enrollment_id")
            or params.get("enrollment")
            or ""
        ).strip()

        batch_id = (
            params.get("batch_id")
            or params.get("batch")
            or ""
        ).strip()

        academic_class_id = (
            params.get("academic_class_id")
            or params.get("academic_class")
            or ""
        ).strip()

        section_id = (
            params.get("section_id")
            or params.get("section")
            or ""
        ).strip()

        payment_status = (
            params.get("status")
            or ""
        ).strip()

        payment_method = (
            params.get("payment_method")
            or ""
        ).strip()

        from_date = (
            params.get("from_date")
            or ""
        ).strip()

        to_date = (
            params.get("to_date")
            or ""
        ).strip()

        if student_id:
            queryset = queryset.filter(
                student_id=student_id
            )

        if enrollment_id:
            queryset = queryset.filter(
                enrollment_id=enrollment_id
            )

        if batch_id:
            if not batch_id.isdigit():
                raise ValidationError({
                    "batch_id": [
                        "Batch ID must be an integer."
                    ]
                })

            queryset = queryset.filter(
                batch_id=int(batch_id)
            )

        if academic_class_id:
            queryset = queryset.filter(
                academic_class_id=academic_class_id
            )

        if section_id:
            queryset = queryset.filter(
                enrollment__section_id=section_id
            )

        if payment_status:
            queryset = queryset.filter(
                status=payment_status
            )

        if payment_method:
            queryset = queryset.filter(
                payment_method=payment_method
            )

        if from_date:
            queryset = queryset.filter(
                paid_at__date__gte=from_date
            )

        if to_date:
            queryset = queryset.filter(
                paid_at__date__lte=to_date
            )

        return queryset

    @extend_schema(
        request=FeePaymentCreateSerializer,
        responses={
            200: FeePaymentReadSerializer,
            201: FeePaymentReadSerializer,
        },
    )
    def create(
        self,
        request,
        *args,
        **kwargs,
    ):
        serializer = FeePaymentCreateSerializer(
            data=request.data,
            context={"request": request},
        )
        serializer.is_valid(
            raise_exception=True
        )

        data = serializer.validated_data

        payment, created = post_payment(
            school=get_school_for_user(
                request.user
            ),
            enrollment=data["enrollment"],
            actor=request.user,
            amount=data["amount"],
            paid_at=data["paid_at"],
            payment_method=data[
                "payment_method"
            ],
            idempotency_key=data[
                "idempotency_key"
            ],
            invoice_ids=data.get(
                "invoice_ids"
            ),
            auto_allocate=data.get(
                "auto_allocate",
                True,
            ),
            external_reference=data.get(
                "external_reference",
                "",
            ),
            notes=data.get(
                "notes",
                "",
            ),
        )

        return Response(
            {
                "message": (
                    "Payment posted."
                    if created
                    else (
                        "Existing payment returned; "
                        "no duplicate was posted."
                    )
                ),
                "created": created,
                "data": FeePaymentReadSerializer(
                    payment
                ).data,
            },
            status=(
                status.HTTP_201_CREATED
                if created
                else status.HTTP_200_OK
            ),
        )

    @extend_schema(
        responses={
            200: OpenApiResponse(
                description="Payment receipt PDF"
            )
        }
    )
    @action(
        detail=True,
        methods=["get"],
        url_path="receipt-pdf",
    )
    def receipt_pdf(
        self,
        request,
        pk=None,
    ):
        payment = self.get_object()

        return _pdf_response(
            build_payment_receipt_pdf(
                payment
            ),
            f"{payment.receipt_number}.pdf",
        )

    @extend_schema(
        request=FinancialReasonSerializer,
        responses={
            200: FeePaymentReadSerializer
        },
    )
    @action(
        detail=True,
        methods=["post"],
        url_path="reverse",
    )
    def reverse(
        self,
        request,
        pk=None,
    ):
        serializer = FinancialReasonSerializer(
            data=request.data
        )
        serializer.is_valid(
            raise_exception=True
        )

        payment, changed = reverse_payment(
            school=get_school_for_user(
                request.user
            ),
            payment=self.get_object(),
            actor=request.user,
            reason=serializer.validated_data[
                "reason"
            ],
        )

        return Response(
            {
                "message": (
                    "Payment reversed."
                    if changed
                    else (
                        "Payment was already reversed."
                    )
                ),
                "data": FeePaymentReadSerializer(
                    payment
                ).data,
            }
        )

class StudentFeeConcessionViewSet(
    mixins.CreateModelMixin,
    mixins.ListModelMixin,
    mixins.RetrieveModelMixin,
    mixins.UpdateModelMixin,
    viewsets.GenericViewSet,
):
    serializer_class = (
        StudentFeeConcessionSerializer
    )
    pagination_class = MetaPageNumberPagination
    ordering = ["-created_at"]

    def get_permissions(self):
        if self.action in [
            "create",
            "update",
            "partial_update",
            "revoke",
        ]:
            return [
                IsAuthenticatedAndActive(),
                CanManageFeeConcessions(),
            ]

        return [
            IsAuthenticatedAndActive(),
            CanViewFeeManagement(),
        ]

    def get_queryset(self):
        school = get_school_for_user(
            self.request.user
        )

        queryset = (
            StudentFeeConcession.objects
            .select_related(
                "student",
                "batch",
                "academic_class",
                "fee_head",
                "approved_by",
                "revoked_by",
            )
            .filter(
                school=school
            )
        )

        params = self.request.query_params

        student_id = params.get("student_id")
        concession_status = params.get(
            "status"
        )

        if student_id:
            queryset = queryset.filter(
                student_id=student_id
            )

        if concession_status:
            queryset = queryset.filter(
                status=concession_status
            )

        return queryset

    def perform_create(
        self,
        serializer,
    ):
        concession = serializer.save()

        audit(
            school=concession.school,
            actor=self.request.user,
            event_type="CONCESSION_CREATED",
            entity=concession,
            payload={
                "kind": concession.kind,
                "value": str(
                    concession.value
                ),
                "reason": concession.reason,
            },
        )

    def perform_update(
        self,
        serializer,
    ):
        concession = serializer.save()

        audit(
            school=concession.school,
            actor=self.request.user,
            event_type="CONCESSION_UPDATED",
            entity=concession,
            payload={
                "kind": concession.kind,
                "value": str(
                    concession.value
                ),
                "reason": concession.reason,
            },
        )

    @extend_schema(
        request=FinancialReasonSerializer,
        responses={
            200: StudentFeeConcessionSerializer
        },
    )
    @action(
        detail=True,
        methods=["post"],
        url_path="revoke",
    )
    def revoke(
        self,
        request,
        pk=None,
    ):
        serializer = FinancialReasonSerializer(
            data=request.data
        )
        serializer.is_valid(
            raise_exception=True
        )

        concession = self.get_object()

        if (
            concession.status
            == ConcessionStatus.REVOKED
        ):
            return Response(
                {
                    "message": (
                        "Concession was already revoked."
                    ),
                    "data": self.get_serializer(
                        concession
                    ).data,
                }
            )

        concession.status = (
            ConcessionStatus.REVOKED
        )
        concession.revoked_by = request.user
        concession.revoked_at = timezone.now()
        concession.revoke_reason = (
            serializer.validated_data[
                "reason"
            ]
        )

        concession.save(
            update_fields=[
                "status",
                "revoked_by",
                "revoked_at",
                "revoke_reason",
                "updated_at",
            ]
        )

        audit(
            school=concession.school,
            actor=request.user,
            event_type="CONCESSION_REVOKED",
            entity=concession,
            payload={
                "reason": (
                    concession.revoke_reason
                )
            },
        )

        return Response(
            {
                "message": "Concession revoked.",
                "data": self.get_serializer(
                    concession
                ).data,
            }
        )


class FeeAdvanceCreditViewSet(
    viewsets.ReadOnlyModelViewSet
):
    serializer_class = (
        FeeAdvanceCreditReadSerializer
    )
    pagination_class = MetaPageNumberPagination
    permission_classes = [
        IsAuthenticatedAndActive,
        CanViewFeeManagement,
    ]
    ordering = ["-created_at"]

    def get_queryset(self):
        school = get_school_for_user(
            self.request.user
        )

        queryset = (
            FeeAdvanceCredit.objects
            .select_related(
                "student",
                "enrollment",
                "payment",
            )
            .prefetch_related(
                "applications__invoice"
            )
            .filter(
                school=school
            )
        )

        params = self.request.query_params

        student_id = params.get("student_id")
        enrollment_id = params.get(
            "enrollment_id"
        )
        credit_status = params.get("status")

        if student_id:
            queryset = queryset.filter(
                student_id=student_id
            )

        if enrollment_id:
            queryset = queryset.filter(
                enrollment_id=enrollment_id
            )

        if credit_status:
            queryset = queryset.filter(
                status=credit_status
            )

        return queryset


class FeeConfigurationAPIView(APIView):
    permission_classes = [
        IsAuthenticatedAndActive,
        CanManageFeeConcessions,
    ]

    def get(self, request):
        school = get_school_for_user(
            request.user
        )

        config = get_fee_configuration(
            school
        )

        return Response(
            {
                "data": FeeConfigurationSerializer(
                    config
                ).data
            }
        )

    def patch(self, request):
        school = get_school_for_user(
            request.user
        )

        with transaction.atomic():
            config = get_fee_configuration(
                school
            )

            before = FeeConfigurationSerializer(
                config
            ).data

            serializer = FeeConfigurationSerializer(
                config,
                data=request.data,
                partial=True,
            )
            serializer.is_valid(
                raise_exception=True
            )

            old_currency = config.currency
            config = serializer.save()

            if config.currency != old_currency:
                from fees.models import (
                    FeeStructure,
                )

                FeeStructure.objects.filter(
                    school=school
                ).update(
                    currency=config.currency
                )

            audit(
                school=school,
                actor=request.user,
                event_type=(
                    "FEE_CONFIGURATION_UPDATED"
                ),
                entity=config,
                payload={
                    "before": before,
                    "after": serializer.data,
                },
            )

        return Response(
            {
                "message": (
                    "Fee configuration updated."
                ),
                "data": serializer.data,
            }
        )


class StudentFeeAccountAPIView(APIView):
    permission_classes = [
        IsAuthenticatedAndActive,
        CanViewFeeManagement,
    ]

    def get(
        self,
        request,
        enrollment_id,
    ):
        school = get_school_for_user(
            request.user
        )

        enrollment = (
            StudentEnrollments.objects
            .select_related(
                "student",
                "batch__school",
                "academic_class",
            )
            .filter(
                id=enrollment_id,
                batch__school=school,
            )
            .first()
        )

        if not enrollment:
            return Response(
                {
                    "enrollment_id": [
                        (
                            "Enrollment not found "
                            "in your school."
                        )
                    ]
                },
                status=status.HTTP_404_NOT_FOUND,
            )

        wallet = rebuild_wallet(
            enrollment=enrollment
        )

        invoices = (
            FeeInvoice.objects
            .filter(
                enrollment=enrollment
            )
            .order_by(
                "-invoice_date",
                "-created_at",
            )[:20]
        )

        payments = (
            FeePayment.objects
            .filter(
                enrollment=enrollment
            )
            .order_by(
                "-paid_at",
                "-created_at",
            )[:20]
        )

        advances = (
            FeeAdvanceCredit.objects
            .select_related(
                "payment"
            )
            .prefetch_related(
                "applications__invoice"
            )
            .filter(
                enrollment=enrollment
            )
            .order_by(
                "-created_at"
            )[:20]
        )

        return Response(
            {
                "wallet": (
                    StudentFeeWalletSerializer(
                        wallet
                    ).data
                ),
                "recent_invoices": (
                    FeeInvoiceReadSerializer(
                        invoices,
                        many=True,
                    ).data
                ),
                "recent_payments": (
                    FeePaymentReadSerializer(
                        payments,
                        many=True,
                    ).data
                ),
                "advance_credits": (
                    FeeAdvanceCreditReadSerializer(
                        advances,
                        many=True,
                    ).data
                ),
            }
        )