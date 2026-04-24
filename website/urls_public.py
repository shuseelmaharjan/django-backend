from django.urls import path
from .views_public import (PublicHomepageAPIView, PublicNavigationCoursesAPIView,
                           PublicCourseDetailAPIView, PublicCareersAPIView, PublicAboutUsAPIView, PublicGalleryAPIView,
                           PublicAllCoursesByNavigationAPIView, PublicCourseSearchSuggestionsAPIView)

urlpatterns = [
    path("v1/<slug:school_code>/homepage/", PublicHomepageAPIView.as_view(), name="public-homepage"),

    path(
        "v1/<slug:school_code>/courses/search-suggestions/",
        PublicCourseSearchSuggestionsAPIView.as_view(),
        name="public-course-search-suggestions",
    ),

    path(
        "v1/<slug:school_code>/courses/",
        PublicAllCoursesByNavigationAPIView.as_view(),
        name="public-all-courses-by-navigation",
    ),

    path(
        "v1/<slug:school_code>/courses/<slug:navigation_slug>/",
        PublicNavigationCoursesAPIView.as_view(),
        name="public-navigation-courses",
    ),

    path(
        "v1/<slug:school_code>/course/<slug:course_slug>/",
        PublicCourseDetailAPIView.as_view(),
        name="public-course-detail",
    ),

    path("v1/<slug:school_code>/careers/", PublicCareersAPIView.as_view(), name="public-careers"),
    path("v1/<slug:school_code>/about-us/", PublicAboutUsAPIView.as_view(), name="public-about-us"),
    path("v1/<slug:school_code>/gallery/", PublicGalleryAPIView.as_view(), name="public-gallery"),
]