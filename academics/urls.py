# academics/urls.py
from django.urls import path, include
from rest_framework.routers import DefaultRouter

from academics.views import (
    AcademicClassViewSet,
    SectionViewSet,
    StudentEnrollmentViewSet,
    ScheduleViewSet,
)
from academics.pdf_views import SchedulePdfView

router = DefaultRouter()
router.register(r"classrooms", AcademicClassViewSet, basename="classroom")
router.register(r"sections", SectionViewSet, basename="section")
router.register(r"student-enrollments", StudentEnrollmentViewSet, basename="student-enrollment")
router.register(r"schedules", ScheduleViewSet, basename="schedule")

urlpatterns = [
    # put custom path BEFORE router to prevent /schedules/<pk>/ catching "pdf"
    path("schedules/pdf/", SchedulePdfView.as_view(), name="schedule-pdf"),
    path("", include(router.urls)),
]
