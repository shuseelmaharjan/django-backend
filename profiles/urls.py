# profiles/urls.py

from django.urls import path
from rest_framework.routers import DefaultRouter

from .views import (
    TeacherLevelViewSet,
    TeacherSpecializationViewSet,
)
from .views_teachers import TeacherListViewSet
from .views_student_list import StudentListViewSet
from .views_student_360 import Student360ViewSet

from .views_management_profile import (
    ManagedUserCompleteProfileView,
    ManagedUserIdentityUpdateView,
    ManagedUserProfilePictureView,
    ManagedUserPersonalInfoView,
    ManagedUserAddressView,
    ManagedUserGuardianListCreateView,
    ManagedUserGuardianDetailView,
    ManagedUserDocumentListCreateView,
    ManagedUserDocumentDetailView,
    ManagedUserHealthView,
)


app_name = "profiles"


router = DefaultRouter()

router.register(
    r"teacher-levels",
    TeacherLevelViewSet,
    basename="teacher-level",
)

router.register(
    r"teacher-specializations",
    TeacherSpecializationViewSet,
    basename="teacher-specialization",
)

router.register(
    r"teachers",
    TeacherListViewSet,
    basename="teachers",
)

router.register(
    r"students-short-info",
    StudentListViewSet,
    basename="students",
)

router.register(
    r"students-360",
    Student360ViewSet,
    basename="students-360",
)


management_profile_urlpatterns = [
    path(
        "management/users/<uuid:user_id>/profile/",
        ManagedUserCompleteProfileView.as_view(),
        name="management-user-complete-profile",
    ),

    path(
        "management/users/<uuid:user_id>/identity/",
        ManagedUserIdentityUpdateView.as_view(),
        name="management-user-identity",
    ),

    path(
        "management/users/<uuid:user_id>/profile-picture/",
        ManagedUserProfilePictureView.as_view(),
        name="management-user-profile-picture",
    ),

    path(
        "management/users/<uuid:user_id>/personal-info/",
        ManagedUserPersonalInfoView.as_view(),
        name="management-user-personal-info",
    ),

    path(
        "management/users/<uuid:user_id>/addresses/<str:address_type>/",
        ManagedUserAddressView.as_view(),
        name="management-user-address",
    ),

    path(
        "management/users/<uuid:user_id>/guardians/",
        ManagedUserGuardianListCreateView.as_view(),
        name="management-user-guardian-list-create",
    ),

    path(
        "management/users/<uuid:user_id>/guardians/<uuid:guardian_id>/",
        ManagedUserGuardianDetailView.as_view(),
        name="management-user-guardian-detail",
    ),

    path(
        "management/users/<uuid:user_id>/documents/",
        ManagedUserDocumentListCreateView.as_view(),
        name="management-user-document-list-create",
    ),

    path(
        "management/users/<uuid:user_id>/documents/<uuid:document_id>/",
        ManagedUserDocumentDetailView.as_view(),
        name="management-user-document-detail",
    ),

    path(
        "management/users/<uuid:user_id>/health/",
        ManagedUserHealthView.as_view(),
        name="management-user-health",
    ),
]


urlpatterns = router.urls + management_profile_urlpatterns