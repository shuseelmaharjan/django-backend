# profiles/views_teachers.py
from __future__ import annotations

from django.db.models import Prefetch
from drf_spectacular.utils import extend_schema, extend_schema_view, OpenApiParameter
from rest_framework import mixins, viewsets
from rest_framework.permissions import IsAuthenticated
from rest_framework.exceptions import ValidationError

from accounts.models import User
from common.constants import UserRole, UserStatus
from common.pagination import MetaPageNumberPagination
from common.mixins import ListFilterMetaMixin
from common.permissions import IsSchoolManagement
from utils.get_school_id_by_token import get_school_for_user

from profiles.models import Profile, TeacherSpecialization, ProfileDocument
from profiles.serializers_teacher_list import TeacherFullSerializer


@extend_schema_view(
    list=extend_schema(
        operation_id="teachers_list",
        tags=["Teachers"],
        parameters=[
            OpenApiParameter(
                name="teacher_level",
                description="Filter by TeacherLevel id (UUID).",
                required=False,
                type=str,
            ),
            OpenApiParameter(
                name="has_level",
                description="true/false. If true => only teachers with a level. If false => only teachers without a level.",
                required=False,
                type=str,
            ),
            OpenApiParameter(
                name="search",
                description="Search by name/phone/email (uses ListFilterMetaMixin conventions).",
                required=False,
                type=str,
            ),
        ],
        responses={200: TeacherFullSerializer(many=True)},
    )
)
class TeacherListViewSet(
    ListFilterMetaMixin,
    mixins.ListModelMixin,
    mixins.RetrieveModelMixin,
    viewsets.GenericViewSet,
):
    permission_classes = [IsAuthenticated, IsSchoolManagement]
    serializer_class = TeacherFullSerializer
    pagination_class = MetaPageNumberPagination
    lookup_field = "id"

    search_fields = ["first_name", "middle_name", "last_name", "phone", "email"]
    searchable_fields = search_fields
    search_param_name = "search"

    ordering_param_name = "ordering"
    ordering_fields = ["first_name", "last_name", "phone", "created_at"]
    public_sort_meta = {
        "first_name": "First name",
        "last_name": "Last name",
        "phone": "Phone",
        "created_at": "Created at",
    }
    sortable_fields = public_sort_meta

    public_filter_meta = {
        "teacher_level": "Teacher level id (UUID)",
        "has_level": "Has teacher level (true/false)",
    }
    filterable_fields = public_filter_meta

    def _teacher_level_filter(self):
        return (self.request.query_params.get("teacher_level") or "").strip()

    def _has_level_filter(self):
        return (self.request.query_params.get("has_level") or "").strip().lower()

    def _subject_id_filter(self):
        return (self.request.query_params.get("subject_id") or "").strip()

    def get_queryset(self):
        school = get_school_for_user(self.request.user)

        qs = (
            User.objects
            .filter(
                role=UserRole.TEACHER,
                status=UserStatus.ACTIVE,
                is_deleted=False,
                profile__school=school,     # ✅ ensures Profile exists + school scoped
            )
            .select_related(
                "profile",
                "profile_picture_file",     # ✅ if you want profile picture file info
            )
        )

        # Teacher specialization (unique per user) + level + subjects
        teacher_spec_qs = (
            TeacherSpecialization.objects
            .select_related("teacher_level")
            .prefetch_related("subjects")
        )
        qs = qs.prefetch_related(
            Prefetch("teacher_specializations", queryset=teacher_spec_qs)
        )
        subject_id = self._subject_id_filter()
        if subject_id:
            qs = qs.filter(teacher_specializations__subjects__id=subject_id)

        # Profile relations
        qs = qs.prefetch_related(
            "profile__addresses",
            "profile__guardians",
            Prefetch(
                "profile__documents",
                queryset=ProfileDocument.objects.select_related("file"),
            ),
        )

        # Filters
        teacher_level_id = self._teacher_level_filter()
        if teacher_level_id:
            qs = qs.filter(teacher_specializations__teacher_level_id=teacher_level_id)

        has_level = self._has_level_filter()
        if has_level in ("true", "1", "yes"):
            qs = qs.filter(teacher_specializations__teacher_level__isnull=False)
        elif has_level in ("false", "0", "no"):
            qs = qs.filter(teacher_specializations__teacher_level__isnull=True)
        elif has_level in ("", None):
            pass
        else:
            raise ValidationError({"has_level": ["Invalid value. Use true/false."]})

        return qs.distinct()