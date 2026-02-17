from __future__ import annotations

from django.db.models import Prefetch
from rest_framework import mixins, viewsets
from rest_framework.exceptions import ValidationError
from rest_framework.response import Response

from common.pagination import MetaPageNumberPagination
from common.permissions import IsAuthenticatedAndActive, IsSchoolManagement
from utils.get_school_id_by_token import get_school_for_user

from accounts.models import User
from common.constants import UserRole

from profiles.models import ProfileDocument, StudentOtherInfo
from academics.models import StudentEnrollments
from batch.models import AcademicBatch

from billing.models import Billing
from fees.models import FeeStructure, FeeInclude, StudentFeeWallet, FeeIncludeAudit, FeeStatus
from drf_spectacular.utils import (
    extend_schema,
    extend_schema_view,
    OpenApiParameter,
    OpenApiTypes,
    OpenApiExample,
)
from django.db.models import Q
from profiles.serializers_student_360 import (
    Student360SummarySerializer,
    Student360DetailSerializer,
)

TRUE_VALUES = {"true", "1", "yes"}
FALSE_VALUES = {"false", "0", "no"}

PARAM_BATCH = OpenApiParameter(
    name="batch",
    type=OpenApiTypes.INT,
    location=OpenApiParameter.QUERY,
    required=False,
    description="Scope results to a batch id (int). For list: students who have any enrollment in this batch. For retrieve: filters scoped data to this batch.",
)

PARAM_ENROLLMENT_STATUS = OpenApiParameter(
    name="enrollment_status",
    type=OpenApiTypes.STR,
    location=OpenApiParameter.QUERY,
    required=False,
    description="Filter by enrollment status. Example: enrolled, dropped, graduated, suspended, alumni.",
)

PARAM_INCLUDE_ALL_ENROLLMENTS = OpenApiParameter(
    name="include_all_enrollments",
    type=OpenApiTypes.BOOL,
    location=OpenApiParameter.QUERY,
    required=False,
    description="(Retrieve only) If false, the `enrollments` array is filtered using the same batch/status scope. Default: true.",
)


@extend_schema_view(
    list=extend_schema(
        operation_id="students_360_list",
        tags=["Students"],
        summary="List students (summary)",
        description=(
            "Returns summary info only.\n\n"
            "- Always scoped to the authenticated user's school.\n"
            "- Supports filtering by batch and enrollment status.\n"
            "- `batches_meta` shows which batches each student has ever existed in."
        ),
        parameters=[
            PARAM_BATCH,
            PARAM_ENROLLMENT_STATUS,
        ],
        responses={200: Student360SummarySerializer(many=True)},
        examples=[
            OpenApiExample(
                "List students in a batch",
                description="Students who have at least one enrollment in batch=2021",
                value={"batch": 2021},
                request_only=True,
            ),
        ],
    ),
    retrieve=extend_schema(
        operation_id="students_360_retrieve",
        tags=["Students"],
        summary="Retrieve student (full detail)",
        description=(
            "Returns complete student detail, including:\n"
            "- enrollments (batch/class/section)\n"
            "- billings (scoped by date range when batch is provided)\n"
            "- fee_structures, fee_includes, wallets, fee_include_audits\n\n"
            "If `batch` is provided, the response includes `_scope` with notes.\n\n"
            "**Important:** Billing has no batch foreign key. When `batch` is provided, billings are scoped by "
            "`created_at` date range between batch start/end."
        ),
        parameters=[
            PARAM_BATCH,
            PARAM_ENROLLMENT_STATUS,
            PARAM_INCLUDE_ALL_ENROLLMENTS,
        ],
        responses={200: Student360DetailSerializer},
        examples=[
            OpenApiExample(
                "Retrieve full student",
                description="Full student data with no batch scope",
                value={},
                request_only=True,
            ),
            OpenApiExample(
                "Retrieve student scoped to batch",
                description="Scope all related data to batch=2021",
                value={"batch": 2021},
                request_only=True,
            ),
        ],
    ),
)
class Student360ViewSet(
    mixins.ListModelMixin,
    mixins.RetrieveModelMixin,
    viewsets.GenericViewSet,
):
    """
    LIST  /students-360/        -> summary info only
    GET   /students-360/<id>/   -> full detail (optionally batch-scoped)

    Query params:
      - batch=<int>                 (optional; scope data to one batch)
      - enrollment_status=<status>  (optional; filters enrollments used for scoping)
      - include_all_enrollments=true/false  (optional; default true in retrieve)
    """
    permission_classes = [IsAuthenticatedAndActive, IsSchoolManagement]
    pagination_class = MetaPageNumberPagination
    lookup_field = "id"

    def _p(self, key: str) -> str:
        return (self.request.query_params.get(key) or "").strip()

    def _bool(self, key: str, default: bool = False) -> bool:
        v = self._p(key).lower()
        if not v:
            return default
        if v in TRUE_VALUES:
            return True
        if v in FALSE_VALUES:
            return False
        raise ValidationError({key: ["Invalid boolean. Use true/false."]})

    def get_serializer_class(self):
        if self.action == "list":
            return Student360SummarySerializer
        return Student360DetailSerializer

    def get_queryset(self):
        school = get_school_for_user(self.request.user)

        qs = (
            User.objects.filter(
                role=UserRole.STUDENT,
                is_deleted=False,
                profile__school=school,
            )
            .select_related("profile", "profile_picture_file")
        )

        # Prefetch profile relations
        qs = qs.prefetch_related(
            "profile__addresses",
            "profile__guardians",
            Prefetch(
                "profile__documents",
                queryset=ProfileDocument.objects.select_related("file"),
            ),
            Prefetch(
                "profile__student_other_info",
                queryset=StudentOtherInfo.objects.all(),
            ),
        )

        # Prefetch enrollments ordered newest first (used for current_enrollment and meta)
        enroll_qs = (
            StudentEnrollments.objects.select_related("batch", "academic_class", "section")
            .order_by("-enrolled_at")
        )
        qs = qs.prefetch_related(Prefetch("enrollments", queryset=enroll_qs))

        # Optional: list filter to show only "enrolled" students (your request)
        # You can still pass enrollment_status=graduated/dropped etc when needed.
        enrollment_status = self._p("enrollment_status")
        if enrollment_status:
            qs = qs.filter(enrollments__status=enrollment_status)

        # batch filter for listing (who exists in that batch)
        batch_id = self._p("batch")
        if batch_id:
            if not batch_id.isdigit():
                raise ValidationError({"batch": ["Batch must be an integer."]})
            qs = qs.filter(enrollments__batch_id=int(batch_id))

        return qs.distinct()

    def list(self, request, *args, **kwargs):
        """
        Summary only.
        """
        return super().list(request, *args, **kwargs)

    def retrieve(self, request, *args, **kwargs):
        """
        Full detail. Supports batch-scoped detail via ?batch=<id>
        """
        student: User = self.get_object()

        # Security sanity
        if student.role != UserRole.STUDENT:
            raise ValidationError({"user": ["User is not a student."]})

        school = get_school_for_user(request.user)
        if getattr(student, "profile", None) and student.profile.school_id != school.id:
            raise ValidationError({"user": ["Student does not belong to your school."]})

        batch_id_str = self._p("batch")
        enrollment_status = self._p("enrollment_status")
        include_all_enrollments = self._bool("include_all_enrollments", default=True)

        batch = None
        if batch_id_str:
            if not batch_id_str.isdigit():
                raise ValidationError({"batch": ["Batch must be an integer."]})
            batch = AcademicBatch.objects.filter(id=int(batch_id_str)).first()
            if not batch:
                raise ValidationError({"batch": ["Batch not found."]})
            if batch.school_id != school.id:
                raise ValidationError({"batch": ["Batch does not belong to your school."]})

        # -----------------------------
        # Enrollments: scope / filter
        # -----------------------------
        enrollments_qs = student.enrollments.all()  # prefetched ordered desc

        if batch:
            enrollments_qs = enrollments_qs.filter(batch_id=batch.id)

        if enrollment_status:
            enrollments_qs = enrollments_qs.filter(status=enrollment_status)

        # If scoping by batch, we can infer relevant class ids
        class_ids = list(
            enrollments_qs.values_list("academic_class_id", flat=True)
        )
        class_ids = [cid for cid in class_ids if cid]

        # -----------------------------
        # Billing scoping (IMPORTANT NOTE)
        # -----------------------------
        # Billing has NO batch/class FK. So we approximate:
        # if batch is given -> billings between batch.start_date_ad and batch.end_date_ad
        billings_qs = Billing.objects.filter(student_id=student.id).order_by("-created_at")
        if batch:
            billings_qs = billings_qs.filter(
                created_at__date__gte=batch.start_date_ad,
                created_at__date__lte=batch.end_date_ad,
            )

        # -----------------------------
        # Fees scoping
        # -----------------------------
        # FeeInclude is already scoped by batch+classroom, so perfect.
        fee_includes_qs = FeeInclude.objects.filter(user_id=student.id).select_related(
            "fees", "fees__fee_head", "batch", "classroom"
        ).order_by("-created_at")

        if batch:
            fee_includes_qs = fee_includes_qs.filter(batch_id=batch.id)
        if class_ids:
            fee_includes_qs = fee_includes_qs.filter(classroom_id__in=class_ids)

        # FeeStructure: "all records" relevant to the student's school and optionally batch/class
        fee_structures_qs = FeeStructure.objects.filter(school_id=school.id).select_related(
            "fee_head", "batch", "academic_class"
        ).order_by("-created_at")

        if batch:
            # include GLOBAL + batch-scoped + batch_class scoped
            fee_structures_qs = fee_structures_qs.filter(
                # GLOBAL has batch/class null. We include it always.
                # For batch scope: match batch OR global
                (Q(batch_id=batch.id) | Q(batch__isnull=True))
            )

        if class_ids:
            # include class-scoped + batch_class-scoped + global/batch-only
            fee_structures_qs = fee_structures_qs.filter(
                Q(academic_class_id__in=class_ids) | Q(academic_class__isnull=True)
            )

        # Wallet: perfectly scoped by student+batch+class
        wallets_qs = StudentFeeWallet.objects.filter(student_id=student.id).order_by("-updated_at")
        if batch:
            wallets_qs = wallets_qs.filter(batch_id=batch.id)
        if class_ids:
            wallets_qs = wallets_qs.filter(academic_class_id__in=class_ids)

        # FeeIncludeAudit: audits for that student's includes
        fee_include_ids = list(fee_includes_qs.values_list("id", flat=True))
        fee_include_audits_qs = FeeIncludeAudit.objects.filter(fee_include_id__in=fee_include_ids).order_by("-created_at")

        # -----------------------------
        # Build serializer context
        # -----------------------------
        context = self.get_serializer_context()
        context.update(
            {
                "billings_qs": billings_qs,
                "fee_structures_qs": fee_structures_qs,
                "fee_includes_qs": fee_includes_qs,
                "wallets_qs": wallets_qs,
                "fee_include_audits_qs": fee_include_audits_qs,
            }
        )

        # Override enrollments on object dynamically:
        # easiest is to attach an attribute used by serializer, but we used related manager.
        # So we pass include_all_enrollments by controlling prefetch? We'll just handle by context:
        # (Simple approach: if not include_all_enrollments, temporarily store filtered list)
        if not include_all_enrollments:
            # Replace with filtered list (serializer expects obj.enrollments manager)
            # We'll pass filtered list in context and adjust serializer quickly:
            context["enrollments_override"] = list(enrollments_qs)

        serializer = self.get_serializer(student, context=context)

        data = serializer.data

        # Patch enrollments if needed (because serializer reads obj.enrollments)
        if not include_all_enrollments:
            from profiles.serializers_student_360 import EnrollmentSerializer
            data["enrollments"] = EnrollmentSerializer(
                context["enrollments_override"], many=True, context=context
            ).data

        # Add meta about scope
        data["_scope"] = {
            "batch": batch.id if batch else None,
            "enrollment_status": enrollment_status or None,
            "billing_scope_note": (
                "Billing is scoped by created_at date range because Billing has no batch FK."
                if batch
                else "Billing includes all records (no batch filter applied)."
            ),
        }

        return Response(data)
