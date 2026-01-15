# from rest_framework import viewsets, status
# from rest_framework.decorators import action
# from rest_framework.response import Response
# from drf_spectacular.utils import extend_schema, OpenApiExample
#
# from common.viewsets import SchoolScopedModelViewSet
# from accounts.permissions import IsSchoolAdmin
# from billing.models import Invoice, InvoiceStatus, Payment, Receipt
# from billing.serializers import (
#     InvoiceSerializer, InvoiceCreateFromChargesSerializer,
#     PaymentSerializer, ReceiptSerializer
# )
# from billing.services import create_invoice_from_charges, allocate_payment, _next_receipt_no
#
#
# @extend_schema(tags=["09. Billing"])
# class InvoiceViewSet(SchoolScopedModelViewSet):
#     queryset = Invoice.objects.select_related("student", "student__user", "academic_year").prefetch_related("lines").all()
#     serializer_class = InvoiceSerializer
#     permission_classes = [IsSchoolAdmin]
#     lookup_field = "id"
#     school_field = "school_id"
#
#     def get_queryset(self):
#         qs = super().get_queryset()
#         student = self.request.query_params.get("student")
#         ay = self.request.query_params.get("academic_year")
#         status_ = self.request.query_params.get("status")
#         if student:
#             qs = qs.filter(student_id=student)
#         if ay:
#             qs = qs.filter(academic_year_id=ay)
#         if status_:
#             qs = qs.filter(status=status_)
#         return qs
#
#     @extend_schema(
#         description="Create invoice from pending StudentCharge items and mark charges as INVOICED.",
#         request=InvoiceCreateFromChargesSerializer,
#         examples=[OpenApiExample("Create from charges", value={
#             "student_id": "UUID",
#             "academic_year_id": "UUID",
#             "invoice_no": "INV-0001",
#             "charge_ids": ["UUID1", "UUID2"]
#         })],
#     )
#     @action(detail=False, methods=["post"])
#     def create_from_charges(self, request):
#         ser = InvoiceCreateFromChargesSerializer(data=request.data)
#         ser.is_valid(raise_exception=True)
#         school_id = request.school_id
#         data = ser.validated_data
#
#         try:
#             inv = create_invoice_from_charges(
#                 school_id=school_id,
#                 student_id=data["student_id"],
#                 academic_year_id=data["academic_year_id"],
#                 invoice_no=data["invoice_no"],
#                 charge_ids=[str(x) for x in data["charge_ids"]],
#             )
#         except ValueError as e:
#             return Response({"detail": str(e)}, status=status.HTTP_400_BAD_REQUEST)
#
#         return Response(InvoiceSerializer(inv).data, status=status.HTTP_201_CREATED)
#
#     @action(detail=True, methods=["post"])
#     def issue(self, request, id=None):
#         inv = self.get_object()
#         if inv.status != InvoiceStatus.DRAFT:
#             return Response({"detail": "Only DRAFT invoices can be issued."}, status=status.HTTP_400_BAD_REQUEST)
#         inv.status = InvoiceStatus.ISSUED
#         inv.save(update_fields=["status"])
#         return Response({"detail": "Issued"}, status=status.HTTP_200_OK)
#
#     @action(detail=True, methods=["post"])
#     def void(self, request, id=None):
#         inv = self.get_object()
#         if inv.status == InvoiceStatus.VOID:
#             return Response({"detail": "Already void."}, status=status.HTTP_400_BAD_REQUEST)
#
#         reason = (request.data or {}).get("reason", "").strip()
#         inv.status = InvoiceStatus.VOID
#         inv.void_reason = reason
#         inv.voided_by = request.user
#         inv.voided_at = request._request._current_scheme_host and inv.voided_at  # noop placeholder
#         # safer:
#         from django.utils import timezone
#         inv.voided_at = timezone.now()
#         inv.save(update_fields=["status", "void_reason", "voided_by", "voided_at"])
#         return Response({"detail": "Voided"}, status=status.HTTP_200_OK)
#
#
# @extend_schema(tags=["09. Billing"])
# class PaymentViewSet(SchoolScopedModelViewSet):
#     queryset = Payment.objects.select_related("student", "student__user").prefetch_related("allocations").all().order_by("-payment_date")
#     serializer_class = PaymentSerializer
#     permission_classes = [IsSchoolAdmin]
#     lookup_field = "id"
#     school_field = "school_id"
#
#     def get_queryset(self):
#         qs = super().get_queryset()
#         student = self.request.query_params.get("student")
#         if student:
#             qs = qs.filter(student_id=student)
#         return qs
#
#     @extend_schema(
#         description="Allocate a payment to one or more invoices.",
#         examples=[OpenApiExample("Allocate", value={"allocations": [{"invoice_id": "UUID", "amount": "500.00"}]})],
#     )
#     @action(detail=True, methods=["post"])
#     def allocate(self, request, id=None):
#         pay = self.get_object()
#         allocations = (request.data or {}).get("allocations") or []
#         if not isinstance(allocations, list) or not allocations:
#             return Response({"detail": "allocations[] required."}, status=status.HTTP_400_BAD_REQUEST)
#
#         try:
#             result = allocate_payment(payment=pay, allocations=allocations)
#         except Exception as e:
#             return Response({"detail": str(e)}, status=status.HTTP_400_BAD_REQUEST)
#
#         return Response({"detail": "Allocated", "result": result}, status=status.HTTP_200_OK)
#
#
# @extend_schema(tags=["09. Billing"])
# class ReceiptViewSet(SchoolScopedModelViewSet):
#     queryset = Receipt.objects.select_related("payment", "payment__student").all().order_by("-created_at")
#     serializer_class = ReceiptSerializer
#     permission_classes = [IsSchoolAdmin]
#     lookup_field = "id"
#     school_field = "school_id"
#
#     @action(detail=False, methods=["post"])
#     def generate(self, request):
#         """
#         POST body: { "payment_id": "UUID" }
#         Conditions:
#         - One receipt per payment (OneToOne)
#         """
#         school_id = request.school_id
#         payment_id = (request.data or {}).get("payment_id")
#
#         if not payment_id:
#             return Response({"detail": "payment_id required."}, status=status.HTTP_400_BAD_REQUEST)
#
#         pay = Payment.objects.filter(id=payment_id, school_id=school_id).first()
#         if not pay:
#             return Response({"detail": "Payment not found."}, status=status.HTTP_404_NOT_FOUND)
#
#         existing = Receipt.objects.filter(payment=pay).first()
#         if existing:
#             return Response(ReceiptSerializer(existing).data, status=status.HTTP_200_OK)
#
#         receipt = Receipt.objects.create(
#             school_id=school_id,
#             payment=pay,
#             receipt_no=_next_receipt_no(school_id),
#         )
#         return Response(ReceiptSerializer(receipt).data, status=status.HTTP_201_CREATED)
