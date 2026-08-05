from __future__ import annotations

from functools import reduce
from operator import and_

from django.db.models import Prefetch, Q
from rest_framework import mixins, viewsets
from rest_framework.exceptions import ValidationError
from rest_framework.response import Response

from accounts.models import User
from academics.models import StudentEnrollments
from batch.models import AcademicBatch
from billing.models import Billing
from common.constants import UserRole
from common.pagination import MetaPageNumberPagination
from common.permissions import (
    IsAuthenticatedAndActive,
    IsSchoolManagement,
)
from fees.models import (
    FeeInclude,
    FeeIncludeAudit,
    FeeStructure,
    StudentFeeWallet,
)
from profiles.models import (
    ProfileDocument,
    StudentOtherInfo,
)
from profiles.serializers_student_360 import (
    Student360DetailSerializer,
    Student360SummarySerializer,
)
from utils.get_school_id_by_token import get_school_for_user


TRUE_VALUES = {
    "true",
    "1",
    "yes",
}

FALSE_VALUES = {
    "false",
    "0",
    "no",
}


class Student360ViewSet(
    mixins.ListModelMixin,
    mixins.RetrieveModelMixin,
    viewsets.GenericViewSet,
):
    """
    LIST /students-360/
        Returns paginated student summary records.

    GET /students-360/<id>/
        Returns full detail for one student.

    Supported list query parameters:
        search
        batch or batch_id
        academic_class or academic_class_id
        section or section_id
        enrollment_status
        ordering
        page
        page_size

    Supported search values:
        Student first, middle or last name
        Full name terms
        Username
        Registration number
        Student email
        Student phone
        Guardian name
        Guardian email
        Guardian phone
    """

    permission_classes = [
        IsAuthenticatedAndActive,
        IsSchoolManagement,
    ]

    pagination_class = MetaPageNumberPagination
    lookup_field = "id"

    # Used by pagination/filter metadata.
    search_fields = [
        "first_name",
        "middle_name",
        "last_name",
        "username",
        "registration_no",
        "email",
        "phone",
        "profile__guardians__full_name",
        "profile__guardians__email",
        "profile__guardians__phone",
    ]

    searchable_fields = search_fields
    search_param_name = "search"

    ordering_fields = [
        "first_name",
        "middle_name",
        "last_name",
        "username",
        "registration_no",
        "created_at",
    ]

    sortable_fields = {
        "first_name": "First name",
        "middle_name": "Middle name",
        "last_name": "Last name",
        "username": "Username",
        "registration_no": "Registration number",
        "created_at": "Created at",
    }

    ordering = [
        "first_name",
        "middle_name",
        "last_name",
    ]

    filterable_fields = {
        "batch_id": "Batch ID",
        "academic_class_id": "Academic class UUID",
        "section_id": "Section UUID",
        "enrollment_status": "Enrollment status",
    }

    def _p(self, *keys: str) -> str:
        """
        Return the first non-empty query parameter.

        Supports both legacy and preferred parameter names:
            batch / batch_id
            academic_class / academic_class_id
            section / section_id
        """

        for key in keys:
            value = (
                self.request.query_params.get(key)
                or ""
            ).strip()

            if value:
                return value

        return ""

    def _bool(
        self,
        key: str,
        default: bool = False,
    ) -> bool:
        value = self._p(key).lower()

        if not value:
            return default

        if value in TRUE_VALUES:
            return True

        if value in FALSE_VALUES:
            return False

        raise ValidationError({
            key: [
                "Invalid boolean. Use true or false."
            ]
        })

    def get_serializer_class(self):
        if self.action == "list":
            return Student360SummarySerializer

        return Student360DetailSerializer

    def _apply_student_search(
        self,
        queryset,
        search_value: str,
    ):
        """
        Apply multi-term student and guardian search.

        Example:
            search=Uma Basnet

        becomes:

            term 1: Uma must match at least one searchable field
            AND
            term 2: Basnet must match at least one searchable field

        This prevents unrelated students from being returned.
        """

        terms = [
            term.strip()
            for term in search_value.split()
            if term.strip()
        ]

        if not terms:
            return queryset

        term_queries = []

        for term in terms:
            term_query = (
                Q(first_name__icontains=term)
                | Q(middle_name__icontains=term)
                | Q(last_name__icontains=term)
                | Q(username__icontains=term)
                | Q(registration_no__icontains=term)
                | Q(email__icontains=term)
                | Q(phone__icontains=term)

                # Guardian/parent identity and contacts.
                | Q(
                    profile__guardians__full_name__icontains=term
                )
                | Q(
                    profile__guardians__email__icontains=term
                )
                | Q(
                    profile__guardians__phone__icontains=term
                )
            )

            term_queries.append(term_query)

        return queryset.filter(
            reduce(
                and_,
                term_queries,
            )
        )

    def get_queryset(self):
        school = get_school_for_user(
            self.request.user
        )

        queryset = (
            User.objects
            .filter(
                role=UserRole.STUDENT,
                is_deleted=False,
                profile__school=school,
            )
            .select_related(
                "profile",
                "profile_picture_file",
            )
        )

        queryset = queryset.prefetch_related(
            "profile__addresses",
            "profile__guardians",
            Prefetch(
                "profile__documents",
                queryset=(
                    ProfileDocument.objects
                    .select_related("file")
                ),
            ),
            Prefetch(
                "profile__student_other_info",
                queryset=StudentOtherInfo.objects.all(),
            ),
        )

        enrollment_queryset = (
            StudentEnrollments.objects
            .select_related(
                "batch",
                "academic_class",
                "section",
            )
            .filter(
                batch__school=school,
            )
            .order_by(
                "-enrolled_at"
            )
        )

        queryset = queryset.prefetch_related(
            Prefetch(
                "enrollments",
                queryset=enrollment_queryset,
            )
        )

        # -------------------------------------------------
        # Search
        # -------------------------------------------------

        search_value = self._p("search")

        if search_value:
            queryset = self._apply_student_search(
                queryset,
                search_value,
            )

        # -------------------------------------------------
        # Academic filters
        # -------------------------------------------------

        enrollment_status = self._p(
            "enrollment_status"
        )

        batch_id = self._p(
            "batch_id",
            "batch",
        )

        academic_class_id = self._p(
            "academic_class_id",
            "academic_class",
        )

        section_id = self._p(
            "section_id",
            "section",
        )

        if enrollment_status:
            queryset = queryset.filter(
                enrollments__status=enrollment_status,
                enrollments__batch__school=school,
            )

        if batch_id:
            if not batch_id.isdigit():
                raise ValidationError({
                    "batch_id": [
                        "Batch must be an integer."
                    ]
                })

            queryset = queryset.filter(
                enrollments__batch_id=int(batch_id),
                enrollments__batch__school=school,
            )

        if academic_class_id:
            queryset = queryset.filter(
                enrollments__academic_class_id=(
                    academic_class_id
                ),
                enrollments__batch__school=school,
            )

        if section_id:
            queryset = queryset.filter(
                enrollments__section_id=section_id,
                enrollments__batch__school=school,
            )

        return queryset.distinct()

    def list(
        self,
        request,
        *args,
        **kwargs,
    ):
        return super().list(
            request,
            *args,
            **kwargs,
        )

    def retrieve(
        self,
        request,
        *args,
        **kwargs,
    ):
        student: User = self.get_object()

        if student.role != UserRole.STUDENT:
            raise ValidationError({
                "user": [
                    "User is not a student."
                ]
            })

        school = get_school_for_user(
            request.user
        )

        profile = getattr(
            student,
            "profile",
            None,
        )

        if (
            profile is not None
            and profile.school_id != school.id
        ):
            raise ValidationError({
                "user": [
                    (
                        "Student does not belong "
                        "to your school."
                    )
                ]
            })

        batch_id_string = self._p(
            "batch_id",
            "batch",
        )

        enrollment_status = self._p(
            "enrollment_status"
        )

        include_all_enrollments = self._bool(
            "include_all_enrollments",
            default=True,
        )

        batch = None

        if batch_id_string:
            if not batch_id_string.isdigit():
                raise ValidationError({
                    "batch_id": [
                        "Batch must be an integer."
                    ]
                })

            batch = (
                AcademicBatch.objects
                .filter(
                    id=int(batch_id_string),
                    school=school,
                )
                .first()
            )

            if batch is None:
                raise ValidationError({
                    "batch_id": [
                        (
                            "Batch not found in "
                            "your school."
                        )
                    ]
                })

        enrollments_queryset = (
            student.enrollments
            .filter(
                batch__school=school,
            )
        )

        if enrollment_status:
            enrollments_queryset = (
                enrollments_queryset.filter(
                    status=enrollment_status
                )
            )

        if batch is not None:
            enrollments_queryset = (
                enrollments_queryset.filter(
                    batch_id=batch.id
                )
            )

        class_ids = list(
            enrollments_queryset.values_list(
                "academic_class_id",
                flat=True,
            )
        )

        class_ids = [
            class_id
            for class_id in class_ids
            if class_id
        ]

        billings_queryset = (
            Billing.objects
            .filter(
                student_id=student.id
            )
            .order_by(
                "-created_at"
            )
        )

        if batch is not None:
            billings_queryset = (
                billings_queryset.filter(
                    created_at__date__gte=(
                        batch.start_date_ad
                    ),
                    created_at__date__lte=(
                        batch.end_date_ad
                    ),
                )
            )

        fee_includes_queryset = (
            FeeInclude.objects
            .filter(
                user_id=student.id
            )
            .select_related(
                "fees",
                "fees__fee_head",
                "batch",
                "classroom",
            )
            .order_by(
                "-created_at"
            )
        )

        if batch is not None:
            fee_includes_queryset = (
                fee_includes_queryset.filter(
                    batch_id=batch.id
                )
            )

        if class_ids:
            fee_includes_queryset = (
                fee_includes_queryset.filter(
                    classroom_id__in=class_ids
                )
            )

        fee_structures_queryset = (
            FeeStructure.objects
            .filter(
                school_id=school.id
            )
            .select_related(
                "fee_head",
                "batch",
                "academic_class",
            )
            .order_by(
                "-created_at"
            )
        )

        if batch is not None:
            fee_structures_queryset = (
                fee_structures_queryset.filter(
                    Q(batch_id=batch.id)
                    | Q(batch__isnull=True)
                )
            )

        if class_ids:
            fee_structures_queryset = (
                fee_structures_queryset.filter(
                    Q(
                        academic_class_id__in=(
                            class_ids
                        )
                    )
                    | Q(
                        academic_class__isnull=True
                    )
                )
            )

        wallets_queryset = (
            StudentFeeWallet.objects
            .filter(
                student_id=student.id
            )
            .order_by(
                "-updated_at"
            )
        )

        if batch is not None:
            wallets_queryset = (
                wallets_queryset.filter(
                    batch_id=batch.id
                )
            )

        if class_ids:
            wallets_queryset = (
                wallets_queryset.filter(
                    academic_class_id__in=(
                        class_ids
                    )
                )
            )

        fee_include_ids = list(
            fee_includes_queryset.values_list(
                "id",
                flat=True,
            )
        )

        fee_include_audits_queryset = (
            FeeIncludeAudit.objects
            .filter(
                fee_include_id__in=(
                    fee_include_ids
                )
            )
            .order_by(
                "-created_at"
            )
        )

        context = self.get_serializer_context()

        context.update({
            "billings_qs": billings_queryset,
            "fee_structures_qs": (
                fee_structures_queryset
            ),
            "fee_includes_qs": (
                fee_includes_queryset
            ),
            "wallets_qs": wallets_queryset,
            "fee_include_audits_qs": (
                fee_include_audits_queryset
            ),
        })

        if not include_all_enrollments:
            context["enrollments_override"] = list(
                enrollments_queryset
            )

        serializer = self.get_serializer(
            student,
            context=context,
        )

        data = serializer.data

        if not include_all_enrollments:
            from profiles.serializers_student_360 import (
                EnrollmentSerializer,
            )

            data["enrollments"] = (
                EnrollmentSerializer(
                    context[
                        "enrollments_override"
                    ],
                    many=True,
                    context=context,
                ).data
            )

        data["_scope"] = {
            "batch": (
                batch.id
                if batch is not None
                else None
            ),
            "enrollment_status": (
                enrollment_status or None
            ),
            "billing_scope_note": (
                (
                    "Billing is scoped by created_at "
                    "date range because Billing has "
                    "no batch foreign key."
                )
                if batch is not None
                else (
                    "Billing includes all records; "
                    "no batch filter was applied."
                )
            ),
        }

        return Response(data)