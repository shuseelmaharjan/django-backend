from rest_framework import viewsets, status
from rest_framework.response import Response
from rest_framework.decorators import action
from drf_spectacular.utils import extend_schema, OpenApiExample

from common.viewsets import SchoolScopedModelViewSet
from accounts.permissions import IsSchoolAdmin
from fees.models import FeeHead, FeePlan, FeeRule, StudentFeeOption, StudentFeeOverride, StudentCharge
from fees.serializers import (
    FeeHeadSerializer, FeePlanSerializer, FeeRuleSerializer,
    StudentFeeOptionSerializer, StudentFeeOverrideSerializer, StudentChargeSerializer
)
from fees.services import generate_charges


@extend_schema(tags=["08. Fees"])
class FeeHeadViewSet(SchoolScopedModelViewSet):
    queryset = FeeHead.objects.all().order_by("name")
    serializer_class = FeeHeadSerializer
    permission_classes = [IsSchoolAdmin]
    lookup_field = "id"
    school_field = "school_id"


@extend_schema(tags=["08. Fees"])
class FeePlanViewSet(SchoolScopedModelViewSet):
    queryset = FeePlan.objects.select_related("academic_year").all().order_by("-created_at")
    serializer_class = FeePlanSerializer
    permission_classes = [IsSchoolAdmin]
    lookup_field = "id"
    school_field = "school_id"

    def get_queryset(self):
        qs = super().get_queryset()
        ay = self.request.query_params.get("academic_year")
        if ay:
            qs = qs.filter(academic_year_id=ay)
        return qs


@extend_schema(tags=["08. Fees"])
class FeeRuleViewSet(viewsets.ModelViewSet):
    queryset = FeeRule.objects.select_related("plan", "fee_head").all()
    serializer_class = FeeRuleSerializer
    permission_classes = [IsSchoolAdmin]
    lookup_field = "id"

    def get_queryset(self):
        qs = super().get_queryset()
        school_id = getattr(self.request, "school_id", None)
        if school_id:
            qs = qs.filter(plan__school_id=school_id)

        plan = self.request.query_params.get("plan")
        if plan:
            qs = qs.filter(plan_id=plan)
        return qs


@extend_schema(tags=["08. Fees"])
class StudentFeeOptionViewSet(viewsets.ModelViewSet):
    queryset = StudentFeeOption.objects.select_related("student", "fee_head").all()
    serializer_class = StudentFeeOptionSerializer
    permission_classes = [IsSchoolAdmin]
    lookup_field = "id"

    def get_queryset(self):
        qs = super().get_queryset()
        school_id = getattr(self.request, "school_id", None)
        if school_id:
            qs = qs.filter(student__school_id=school_id)
        student = self.request.query_params.get("student")
        if student:
            qs = qs.filter(student_id=student)
        return qs


@extend_schema(tags=["08. Fees"])
class StudentFeeOverrideViewSet(viewsets.ModelViewSet):
    queryset = StudentFeeOverride.objects.select_related("student", "fee_head").all()
    serializer_class = StudentFeeOverrideSerializer
    permission_classes = [IsSchoolAdmin]
    lookup_field = "id"

    def get_queryset(self):
        qs = super().get_queryset()
        school_id = getattr(self.request, "school_id", None)
        if school_id:
            qs = qs.filter(student__school_id=school_id)
        student = self.request.query_params.get("student")
        if student:
            qs = qs.filter(student_id=student)
        return qs


@extend_schema(tags=["08. Fees"])
class StudentChargeViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = StudentCharge.objects.select_related("student", "student__user", "fee_head").all().order_by("-generated_at")
    serializer_class = StudentChargeSerializer
    permission_classes = [IsSchoolAdmin]
    lookup_field = "id"

    def get_queryset(self):
        qs = super().get_queryset()
        school_id = getattr(self.request, "school_id", None)
        if school_id:
            qs = qs.filter(student__school_id=school_id)

        student = self.request.query_params.get("student")
        status_ = self.request.query_params.get("status")
        ay = self.request.query_params.get("academic_year")
        if student:
            qs = qs.filter(student_id=student)
        if status_:
            qs = qs.filter(status=status_)
        if ay:
            qs = qs.filter(academic_year_id=ay)
        return qs

    @extend_schema(
        description="Generate StudentCharge rows for enrolled students using fee rules.",
        examples=[
            OpenApiExample(
                "Monthly charges for class",
                value={"academic_year_id": "UUID", "month": 5, "academic_class_id": "UUID"},
            )
        ],
    )
    @action(detail=False, methods=["post"])
    def generate(self, request):
        school_id = request.school_id
        payload = request.data or {}

        result = generate_charges(
            school_id=school_id,
            academic_year_id=payload.get("academic_year_id"),
            month=payload.get("month"),
            term_code=payload.get("term_code", "") or "",
            exam_code=payload.get("exam_code", "") or "",
            academic_class_id=payload.get("academic_class_id"),
            section_id=payload.get("section_id"),
        )
        return Response(result, status=status.HTTP_200_OK)
