from __future__ import annotations

from django.db.models import Prefetch
from rest_framework import mixins, viewsets
from rest_framework.exceptions import ValidationError

from accounts.models import User
from academics.models import StudentEnrollments
from common.constants import UserRole
from common.mixins import ListFilterMetaMixin
from common.pagination import MetaPageNumberPagination
from common.permissions import (
    IsAuthenticatedAndActive,
    IsSchoolManagement,
)
from profiles.models import (
    ProfileDocument,
    StudentOtherInfo,
)
from profiles.serializers_student_list import (
    StudentFullSerializer,
)
from utils.get_school_id_by_token import (
    get_school_for_user,
)


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


class StudentListViewSet(
    ListFilterMetaMixin,
    mixins.ListModelMixin,
    mixins.RetrieveModelMixin,
    viewsets.GenericViewSet,
):
    permission_classes = [
        IsAuthenticatedAndActive,
        IsSchoolManagement,
    ]

    serializer_class = StudentFullSerializer
    pagination_class = MetaPageNumberPagination
    lookup_field = "id"

    search_fields = [
        "first_name",
        "middle_name",
        "last_name",
        "username",
        "registration_no",
        "phone",
        "email",
    ]

    searchable_fields = search_fields
    search_param_name = "search"

    ordering_param_name = "ordering"

    ordering_fields = [
        "first_name",
        "middle_name",
        "last_name",
        "username",
        "registration_no",
        "phone",
        "created_at",
    ]

    ordering = [
        "first_name",
        "middle_name",
        "last_name",
    ]

    public_sort_meta = {
        "first_name": "First name",
        "middle_name": "Middle name",
        "last_name": "Last name",
        "username": "Username",
        "registration_no": "Registration number",
        "phone": "Phone",
        "created_at": "Created at",
    }

    sortable_fields = public_sort_meta

    public_filter_meta = {
        "batch_id": "Batch ID",
        "academic_class_id": "Academic class UUID",
        "section_id": "Section UUID",
        "enrollment_status": (
            "Enrollment status: enrolled, dropped, "
            "graduated, suspended or alumni"
        ),
        "has_guardian": "Has guardian: true or false",
        "has_documents": "Has documents: true or false",
        "has_other_info": (
            "Has student other information: true or false"
        ),
    }

    filterable_fields = public_filter_meta

    def _query_param(
        self,
        *names: str,
    ) -> str:
        """
        Return the first non-empty query parameter.

        This preserves compatibility with both old and new frontend
        parameter names, for example:

        batch / batch_id
        academic_class / academic_class_id
        section / section_id
        """

        for name in names:
            value = (
                self.request.query_params.get(name)
                or ""
            ).strip()

            if value:
                return value

        return ""

    def _validate_boolean_filter(
        self,
        *,
        parameter_name: str,
        value: str,
    ) -> bool | None:
        normalized = value.lower()

        if not normalized:
            return None

        if normalized in TRUE_VALUES:
            return True

        if normalized in FALSE_VALUES:
            return False

        raise ValidationError({
            parameter_name: [
                "Invalid value. Use true or false."
            ]
        })

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
                "-enrolled_at",
            )
        )

        queryset = queryset.prefetch_related(
            Prefetch(
                "enrollments",
                queryset=enrollment_queryset,
            )
        )

        batch_id = self._query_param(
            "batch_id",
            "batch",
        )

        academic_class_id = self._query_param(
            "academic_class_id",
            "academic_class",
        )

        section_id = self._query_param(
            "section_id",
            "section",
        )

        enrollment_status = self._query_param(
            "enrollment_status",
            "status",
        )

        if batch_id:
            if not batch_id.isdigit():
                raise ValidationError({
                    "batch_id": [
                        "Batch ID must be an integer."
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

        if enrollment_status:
            queryset = queryset.filter(
                enrollments__status=enrollment_status,
                enrollments__batch__school=school,
            )

        has_guardian_value = self._query_param(
            "has_guardian"
        )

        has_guardian = self._validate_boolean_filter(
            parameter_name="has_guardian",
            value=has_guardian_value,
        )

        if has_guardian is True:
            queryset = queryset.filter(
                profile__guardians__isnull=False
            )

        elif has_guardian is False:
            queryset = queryset.filter(
                profile__guardians__isnull=True
            )

        has_documents_value = self._query_param(
            "has_documents"
        )

        has_documents = self._validate_boolean_filter(
            parameter_name="has_documents",
            value=has_documents_value,
        )

        if has_documents is True:
            queryset = queryset.filter(
                profile__documents__isnull=False
            )

        elif has_documents is False:
            queryset = queryset.filter(
                profile__documents__isnull=True
            )

        has_other_info_value = self._query_param(
            "has_other_info"
        )

        has_other_info = self._validate_boolean_filter(
            parameter_name="has_other_info",
            value=has_other_info_value,
        )

        if has_other_info is True:
            queryset = queryset.filter(
                profile__student_other_info__isnull=False
            )

        elif has_other_info is False:
            queryset = queryset.filter(
                profile__student_other_info__isnull=True
            )

        return queryset.distinct()