"""
URL configuration for server project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/5.2/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static

from drf_spectacular.views import (
    SpectacularAPIView,
    SpectacularSwaggerView,
    SpectacularRedocView,
)


urlpatterns = [
    path("admin/", admin.site.urls),

    # API schema & docs
    path("api/schema/", SpectacularAPIView.as_view(), name="schema"),
    path("api/docs/", SpectacularSwaggerView.as_view(url_name="schema"), name="swagger-ui"),
    path("api/redoc/", SpectacularRedocView.as_view(url_name="schema"), name="redoc", ),

    # Auth
    path("api/auth/", include("authx.urls")),
    # App routes
    path("api/startup/", include("startup.urls")),
    path("api/", include("filehandler.urls")),

    path("api/v1/org/", include("organization.urls")),
    path("api/v1/accounts/", include("accounts.urls_roles")),
    path("api/v1/profile/", include("accounts.urls")),
    path("api/v1/academics/", include("academics.urls")),
    path("api/v1/students/", include("students.urls")),
    path("api/v1/enrollment/", include("enrollment.urls")),
    path("api/staff/", include("staff.urls")),
    path("api/fees/", include("fees.urls")),
    path("api/billing/", include("billing.urls")),
    path("api/v1/staff/", include("staff.urls_attendance")),
    path("api/v1/communication/", include("communication.urls")),
    path("api/v1/assessments/", include("assessments.urls_subjects")),
    path("api/v1/assessments/", include("assessments.urls_subjects")),   # your existing subjects
    path("api/v1/assessments/", include("assessments.urls_core")),       # step 13
    path("api/v1/assessments/", include("assessments.urls_tests")),      # step 14
    path("api/v1/assessments/", include("assessments.urls_attempts")),   # step 15



]

# Serve media files in development only
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)