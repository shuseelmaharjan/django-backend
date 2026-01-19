from django.urls import path

from accounts.admin_onboarding import (
    AdminPersonalInfoCreateView,
    AdminPersonalInfoUpdateView,
    AdminSchoolInfoCreateView,
    AdminSchoolInfoUpdateView,
    AdminClientInfoCreateView,
    AdminClientInfoUpdateView,
    AdminListView,
    AdminDetailView,
    AdminDeleteView,
)

urlpatterns = [
    path("create-admin/personal-info/", AdminPersonalInfoCreateView.as_view()),
    path("create-admin/personal-info/<uuid:user_id>/", AdminPersonalInfoUpdateView.as_view()),

    path("create-admin/school-info/", AdminSchoolInfoCreateView.as_view()),
    path("create-admin/school-info/<uuid:school_id>/", AdminSchoolInfoUpdateView.as_view()),

    path("create-admin/client-info/", AdminClientInfoCreateView.as_view()),
    path("create-admin/client-info/<uuid:user_id>/", AdminClientInfoUpdateView.as_view()),

    path("admins/", AdminListView.as_view()),
    path("admins/<uuid:pk>/", AdminDetailView.as_view()),
    path("admins/<uuid:user_id>/delete/", AdminDeleteView.as_view()),
]
