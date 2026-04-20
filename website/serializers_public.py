from rest_framework import serializers
from filehandler.serializers import UploadedFileSerializer
from .models import (
    Navigation,
    Courses,
    HomepageBanner,
    Icons,
    PrincipalMessage,
    Testimonial,
    Ads,
    Events,
    Blogs,
    FooterGroup,
    FooterLink,
    AboutUs,
    GalleryGroup,
    GalleryImage,
    Careers,
)


class FooterLinkSerializer(serializers.ModelSerializer):
    class Meta:
        model = FooterLink
        fields = [
            "id",
            "name",
            "url",
            "created_at",
        ]


class FooterGroupSerializer(serializers.ModelSerializer):
    links = FooterLinkSerializer(many=True, read_only=True)

    class Meta:
        model = FooterGroup
        fields = [
            "id",
            "name",
            "links",
            "created_at",
        ]


class CourseSerializer(serializers.ModelSerializer):
    image = UploadedFileSerializer(read_only=True)

    class Meta:
        model = Courses
        fields = [
            "id",
            "name",
            "slug",
            "sort_order",
            "is_popular",
            "image",
        ]


class NavigationSerializer(serializers.ModelSerializer):
    class Meta:
        model = Navigation
        fields = [
            "id",
            "name",
            "slug",
            "sort_order",
            "created_at",
        ]


class NavigationCourseTreeSerializer(serializers.ModelSerializer):
    courses = serializers.SerializerMethodField()

    class Meta:
        model = Navigation
        fields = [
            "id",
            "name",
            "slug",
            "sort_order",
            "created_at",
            "courses",
        ]

    def get_courses(self, obj):
        courses = obj.courses.filter(is_popular=True).order_by("sort_order", "created_at")
        return CourseSerializer(courses, many=True).data


class HomepageBannerSerializer(serializers.ModelSerializer):
    image = UploadedFileSerializer(read_only=True)

    class Meta:
        model = HomepageBanner
        fields = [
            "title",
            "subtitle",
            "description",
            "image",
            "sort_order",
            "have_link",
            "link_url",
            "button_link",
        ]


class IconsSerializer(serializers.ModelSerializer):
    image = UploadedFileSerializer(read_only=True)

    class Meta:
        model = Icons
        fields = [
            "id",
            "name",
            "image",
            "sort_order",
        ]


class PrincipalMessageSerializer(serializers.ModelSerializer):
    image = UploadedFileSerializer(read_only=True)

    class Meta:
        model = PrincipalMessage
        fields = [
            "title",
            "message",
            "image",
        ]


class TestimonialSerializer(serializers.ModelSerializer):
    image = UploadedFileSerializer(read_only=True)

    class Meta:
        model = Testimonial
        fields = [
            "name",
            "role",
            "message",
            "image",
            "created_at",
        ]


class AdsSerializer(serializers.ModelSerializer):
    image = UploadedFileSerializer(read_only=True)

    class Meta:
        model = Ads
        fields = [
            "id",
            "title",
            "description",
            "image",
            "link_url",
        ]


class EventsSerializer(serializers.ModelSerializer):
    class Meta:
        model = Events
        fields = [
            "title",
            "description",
            "event_date",
        ]


class BlogsSerializer(serializers.ModelSerializer):
    class Meta:
        model = Blogs
        fields = [
            "id",
            "title",
            "content",
            "author",
            "published_at",
        ]

class CourseFullSerializer(serializers.ModelSerializer):
    image = UploadedFileSerializer(read_only=True)
    banner = UploadedFileSerializer(read_only=True)

    class Meta:
        model = Courses
        fields = [
            "id",
            "name",
            "description",
            "slug",
            "sort_order",
            "tags",
            "is_popular",
            "image",
            "banner",
        ]


class CareersSerializer(serializers.ModelSerializer):
    class Meta:
        model = Careers
        fields = [
            "id",
            "title",
            "position",
            "job_description",
            "requirements",
            "expires_at",
            "created_at",
        ]


class AboutUsSerializer(serializers.ModelSerializer):
    image = UploadedFileSerializer(read_only=True)

    class Meta:
        model = AboutUs
        fields = [
            "id",
            "title",
            "description",
            "image",
            "created_at",
        ]


class GalleryImageSerializer(serializers.ModelSerializer):
    image = UploadedFileSerializer(read_only=True)

    class Meta:
        model = GalleryImage
        fields = [
            "id",
            "image",
            "caption",
            "created_at",
        ]


class GalleryGroupSerializer(serializers.ModelSerializer):
    images = GalleryImageSerializer(many=True, read_only=True)

    class Meta:
        model = GalleryGroup
        fields = [
            "id",
            "name",
            "images",
            "created_at",
        ]