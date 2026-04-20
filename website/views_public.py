from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import AllowAny
from django.db.models import Prefetch
from .mixins import SchoolCodeMixin
from .models import (
    Courses,
    HomepageBanner,
    Icons,
    PrincipalMessage,
    Testimonial,
    Ads,
    Events,
    Blogs,
    FooterGroup,
    Navigation,
    AboutUs,
    GalleryGroup,
    GalleryImage,
    Careers,

)
from .serializers_public import (
    CourseSerializer,
    HomepageBannerSerializer,
    IconsSerializer,
    PrincipalMessageSerializer,
    TestimonialSerializer,
    AdsSerializer,
    EventsSerializer,
    BlogsSerializer,
    FooterGroupSerializer,
    NavigationCourseTreeSerializer,
    NavigationSerializer, CourseFullSerializer,
    AboutUsSerializer, GalleryGroupSerializer, CareersSerializer,

)
from .services_public import build_public_metadata


class PublicHomepageAPIView(SchoolCodeMixin, APIView):
    permission_classes = [AllowAny]
    authentication_classes = []

    def get(self, request, *args, **kwargs):
        school = self.get_school()

        popular_course_tree = Navigation.objects.filter(
            school=school,
            courses__is_popular=True,
        ).distinct().prefetch_related(
            "courses"
        ).order_by("sort_order", "created_at")

        homepage_banners = HomepageBanner.objects.filter(
            school=school
        ).select_related("image").order_by("sort_order", "created_at")

        icons = Icons.objects.filter(
            school=school
        ).select_related("image").order_by("sort_order", "created_at")

        principal_messages = PrincipalMessage.objects.filter(
            school=school
        ).select_related("image").order_by("-created_at")

        testimonials = Testimonial.objects.filter(
            school=school
        ).select_related("image").order_by("-created_at")

        footer_groups = FooterGroup.objects.filter(
            school=school
        ).prefetch_related("links").order_by("created_at")

        # NOTE:
        # Events and Blogs are global in your current models because
        # they do not have school FK in the code you shared.
        events = Events.objects.all().order_by("-event_date", "-created_at")
        blogs = Blogs.objects.all().order_by("-published_at", "-created_at")

        response_data = {
            "meta": build_public_metadata(school),
            "data": {
                "homepage_banners": HomepageBannerSerializer(homepage_banners, many=True).data,
                "popular_courses": NavigationCourseTreeSerializer(popular_course_tree, many=True).data,
                "icons": IconsSerializer(icons, many=True).data,
                "principal_messages": PrincipalMessageSerializer(principal_messages, many=True).data,
                "testimonials": TestimonialSerializer(testimonials, many=True).data,
                "events": EventsSerializer(events, many=True).data,
                "blogs": BlogsSerializer(blogs, many=True).data,
            }
        }

        return Response(response_data)


class PublicNavigationCoursesAPIView(SchoolCodeMixin, APIView):
    permission_classes = [AllowAny]
    authentication_classes = []

    def get(self, request, *args, **kwargs):
        school = self.get_school()
        navigation_slug = kwargs.get("navigation_slug")

        try:
            navigation = Navigation.objects.get(
                slug=navigation_slug,
                school=school,
            )
        except Navigation.DoesNotExist:
            raise NotFound("Navigation not found for this school.")

        courses = Courses.objects.filter(
            school=school,
            navigation=navigation,
        ).select_related(
            "image",
            "banner",
            "navigation",
        ).order_by("sort_order", "created_at")

        return Response({
            "meta": build_public_metadata(school),
            "data": {
                "navigation": NavigationSerializer(navigation).data,
                "courses": CourseSerializer(courses, many=True).data,
            }
        })


class PublicCourseDetailAPIView(SchoolCodeMixin, APIView):
    permission_classes = [AllowAny]
    authentication_classes = []

    def get(self, request, *args, **kwargs):
        school = self.get_school()
        course_slug = kwargs.get("course_slug")

        try:
            course = Courses.objects.select_related(
                "navigation",
                "image",
                "banner",
                "school",
            ).get(
                school=school,
                slug=course_slug,
            )
        except Courses.DoesNotExist:
            raise NotFound("Course not found for this school.")

        return Response({
            "meta": build_public_metadata(school),
            "data": {
                "navigation": NavigationSerializer(course.navigation).data,
                "course": CourseFullSerializer(course).data,
            }
        })

class PublicCareersAPIView(SchoolCodeMixin, APIView):
    permission_classes = [AllowAny]
    authentication_classes = []

    def get(self, request, *args, **kwargs):
        school = self.get_school()

        careers = Careers.objects.filter(
            school=school
        ).order_by("-created_at")

        return Response({
            "meta": build_public_metadata(school),
            "data": {
                "careers": CareersSerializer(careers, many=True).data,
            }
        })


class PublicAboutUsAPIView(SchoolCodeMixin, APIView):
    permission_classes = [AllowAny]
    authentication_classes = []

    def get(self, request, *args, **kwargs):
        school = self.get_school()

        about_us = AboutUs.objects.filter(
            school=school
        ).select_related(
            "image"
        ).order_by("-created_at")

        principal_message = PrincipalMessage.objects.filter(
            school=school
        ).select_related("image"
        ).order_by("-created_at").first()

        return Response({
            "meta": build_public_metadata(school),
            "data": {
                "about_us": AboutUsSerializer(about_us, many=True).data,
                "principal_message": PrincipalMessageSerializer(principal_message).data if principal_message else None,
            }
        })


class PublicGalleryAPIView(SchoolCodeMixin, APIView):
    permission_classes = [AllowAny]
    authentication_classes = []

    def get(self, request, *args, **kwargs):
        school = self.get_school()

        gallery_groups = GalleryGroup.objects.filter(
            school=school
        ).prefetch_related(
            Prefetch(
                "images",
                queryset=GalleryImage.objects.select_related("image").order_by("created_at")
            )
        ).order_by("created_at")

        return Response({
            "meta": build_public_metadata(school),
            "data": {
                "gallery_groups": GalleryGroupSerializer(gallery_groups, many=True).data,
            }
        })