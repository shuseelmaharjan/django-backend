from django.urls import path, include
from rest_framework.routers import DefaultRouter

from website.views import (
    NavigationViewSet,
    CoursesViewSet,
    HomepageBannerViewSet,
    IconsViewSet,
    PrincipalMessageViewSet,
    TestimonialViewSet,
    AdsViewSet,
    CareersViewSet,
    AboutUsViewSet,
    EventsViewSet,
    BlogsViewSet,
    FooterGroupViewSet,
    FooterLinkViewSet,
    GalleryGroupViewSet,
    GalleryImageViewSet,
)

router = DefaultRouter()
router.register(r"v1/navigations", NavigationViewSet, basename="navigation")
router.register(r"v1/courses", CoursesViewSet, basename="courses")
router.register(r"v1/homepage-banners", HomepageBannerViewSet, basename="homepage-banner")
router.register(r"v1/icons", IconsViewSet, basename="icons")
router.register(r"v1/principal-messages", PrincipalMessageViewSet, basename="principal-message")
router.register(r"v1/testimonials", TestimonialViewSet, basename="testimonial")
router.register(r"v1/ads", AdsViewSet, basename="ads")

router.register(r"v1/careers", CareersViewSet, basename="careers")
router.register(r"v1/about-us", AboutUsViewSet, basename="about-us")
router.register(r"v1/events", EventsViewSet, basename="events")
router.register(r"v1/blogs", BlogsViewSet, basename="blogs")
router.register(r"v1/footer-groups", FooterGroupViewSet, basename="footer-group")
router.register(r"v1/footer-links", FooterLinkViewSet, basename="footer-link")
router.register(r"v1/gallery-groups", GalleryGroupViewSet, basename="gallery-group")
router.register(r"v1/gallery-images", GalleryImageViewSet, basename="gallery-image")

urlpatterns = [
    path("", include(router.urls)),
]