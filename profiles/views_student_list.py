from __future__ import annotations

from django.db.models import Prefetch
from rest_framework import mixins, viewsets
from rest_framework.exceptions import ValidationError

from common.mixins import ListFilterMetaMixin
from common.pagination import MetaPageNumberPagination
from common.permissions import IsAuthenticatedAndActive, IsSchoolManagement  # use your existing permission
from utils.get_school_id_by_token import get_school_for_user

from accounts.models import User
from common.constants import UserRole, UserStatus

from profiles.models import ProfileDocument, StudentOtherInfo
from academics.models import StudentEnrollments

from profiles.serializers_student_list import StudentFullSerializer


TRUE_VALUES = {"true", "1", "yes"}
FALSE_VALUES = {"false", "0", "no"}


class StudentListViewSet(
    ListFilterMetaMixin,
    mixins.ListModelMixin,
    mixins.RetrieveModelMixin,
    viewsets.GenericViewSet,
):
    permission_classes = [IsAuthenticatedAndActive, IsSchoolManagement]
    serializer_class = StudentFullSerializer
    pagination_class = MetaPageNumberPagination
    lookup_field = "id"

    search_fields = ["first_name", "middle_name", "last_name", "phone", "email", "username"]
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
        "batch": "Batch id (int)",
        "academic_class": "Class id (UUID)",
        "section": "Section id (UUID)",
        "enrollment_status": "Enrollment status (enrolled/dropped/graduated/suspended/alumni)",
        "has_guardian": "Has guardian (true/false)",
        "has_documents": "Has documents (true/false)",
        "has_other_info": "Has StudentOtherInfo (true/false)",
    }
    filterable_fields = public_filter_meta

    def _p(self, key: str) -> str:
        return (self.request.query_params.get(key) or "").strip()

    def get_queryset(self):
        school = get_school_for_user(self.request.user)

        qs = (
            User.objects
            .filter(
                role=UserRole.STUDENT,
                is_deleted=False,
                profile__school=school,     # ensures profile exists + school-scoped
            )
            .select_related(
                "profile",
                "profile_picture_file",
            )
        )

        # Prefetch profile relations (addresses/guardians/documents/other info)
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

        # Prefetch enrollments (most recent first)
        enroll_qs = (
            StudentEnrollments.objects
            .select_related("batch", "academic_class", "section")
            .order_by("-enrolled_at")
        )
        qs = qs.prefetch_related(Prefetch("enrollments", queryset=enroll_qs))

        # -------------------------
        # Filters (via enrollments)
        # -------------------------
        batch_id = self._p("batch")
        if batch_id:
            if not batch_id.isdigit():
                raise ValidationError({"batch": ["Batch must be an integer."]})
            qs = qs.filter(enrollments__batch_id=int(batch_id))

        academic_class_id = self._p("academic_class")
        if academic_class_id:
            qs = qs.filter(enrollments__academic_class_id=academic_class_id)

        section_id = self._p("section")
        if section_id:
            qs = qs.filter(enrollments__section_id=section_id)

        enrollment_status = self._p("enrollment_status")
        if enrollment_status:
            qs = qs.filter(enrollments__status=enrollment_status)

        # -------------------------
        # Filters (via profile)
        # -------------------------
        has_guardian = self._p("has_guardian").lower()
        if has_guardian in TRUE_VALUES:
            qs = qs.filter(profile__guardians__isnull=False)
        elif has_guardian in FALSE_VALUES:
            qs = qs.filter(profile__guardians__isnull=True)
        elif has_guardian:
            raise ValidationError({"has_guardian": ["Invalid value. Use true/false."]})

        has_documents = self._p("has_documents").lower()
        if has_documents in TRUE_VALUES:
            qs = qs.filter(profile__documents__isnull=False)
        elif has_documents in FALSE_VALUES:
            qs = qs.filter(profile__documents__isnull=True)
        elif has_documents:
            raise ValidationError({"has_documents": ["Invalid value. Use true/false."]})

        has_other_info = self._p("has_other_info").lower()
        if has_other_info in TRUE_VALUES:
            qs = qs.filter(profile__student_other_info__isnull=False)
        elif has_other_info in FALSE_VALUES:
            qs = qs.filter(profile__student_other_info__isnull=True)
        elif has_other_info:
            raise ValidationError({"has_other_info": ["Invalid value. Use true/false."]})

        return qs.distinct()
