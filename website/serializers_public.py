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
        fields = ["id", "name", "url", "created_at"]


class FooterGroupSerializer(serializers.ModelSerializer):
    links = FooterLinkSerializer(many=True, read_only=True)

    class Meta:
        model = FooterGroup
        fields = ["id", "name", "links", "created_at"]



class CourseSerializer(serializers.ModelSerializer):
    image = serializers.SerializerMethodField()

    class Meta:
        model = Courses
        fields = ["id", "name", "slug", "sort_order", "is_popular", "image"]

    def get_image(self, obj):
        if not obj.image:
            return None
        return UploadedFileSerializer(obj.image, context=self.context).data


class NavigationSerializer(serializers.ModelSerializer):
    class Meta:
        model = Navigation
        fields = ["id", "name", "slug", "sort_order", "created_at"]


class NavigationCourseTreeSerializer(serializers.ModelSerializer):
    courses = serializers.SerializerMethodField()

    class Meta:
        model = Navigation
        fields = ["id", "name", "slug", "sort_order", "created_at", "courses"]

    def get_courses(self, obj):
        courses = obj.courses.filter(is_popular=True).order_by("sort_order", "created_at")
        return CourseSerializer(courses, many=True, context=self.context).data


class HomepageBannerSerializer(serializers.ModelSerializer):
    image = serializers.SerializerMethodField()

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

    def get_image(self, obj):
        if not obj.image:
            return None
        return UploadedFileSerializer(obj.image, context=self.context).data


class IconsSerializer(serializers.ModelSerializer):
    image = serializers.SerializerMethodField()

    class Meta:
        model = Icons
        fields = ["id", "name", "image", "sort_order"]

    def get_image(self, obj):
        if not obj.image:
            return None
        return UploadedFileSerializer(obj.image, context=self.context).data


class PrincipalMessageSerializer(serializers.ModelSerializer):
    image = serializers.SerializerMethodField()

    class Meta:
        model = PrincipalMessage
        fields = ["title", "message", "image"]

    def get_image(self, obj):
        if not obj.image:
            return None
        return UploadedFileSerializer(obj.image, context=self.context).data


class TestimonialSerializer(serializers.ModelSerializer):
    image = serializers.SerializerMethodField()

    class Meta:
        model = Testimonial
        fields = ["name", "role", "message", "image", "created_at"]

    def get_image(self, obj):
        if not obj.image:
            return None
        return UploadedFileSerializer(obj.image, context=self.context).data


class AdsSerializer(serializers.ModelSerializer):
    image = serializers.SerializerMethodField()

    class Meta:
        model = Ads
        fields = ["id", "title", "description", "image", "link_url"]

    def get_image(self, obj):
        if not obj.image:
            return None
        return UploadedFileSerializer(obj.image, context=self.context).data


class EventsSerializer(serializers.ModelSerializer):
    class Meta:
        model = Events
        fields = ["title", "description", "event_date"]


class BlogsSerializer(serializers.ModelSerializer):
    class Meta:
        model = Blogs
        fields = ["id", "title", "content", "author", "published_at"]


class CourseFullSerializer(serializers.ModelSerializer):
    image = serializers.SerializerMethodField()
    banner = serializers.SerializerMethodField()

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

    def get_image(self, obj):
        if not obj.image:
            return None
        return UploadedFileSerializer(obj.image, context=self.context).data

    def get_banner(self, obj):
        if not obj.banner:
            return None
        return UploadedFileSerializer(obj.banner, context=self.context).data


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
    image = serializers.SerializerMethodField()

    class Meta:
        model = AboutUs
        fields = ["id", "title", "description", "image", "created_at"]

    def get_image(self, obj):
        if not obj.image:
            return None
        return UploadedFileSerializer(obj.image, context=self.context).data


class GalleryImageSerializer(serializers.ModelSerializer):
    image = serializers.SerializerMethodField()

    class Meta:
        model = GalleryImage
        fields = ["id", "image", "caption", "created_at"]

    def get_image(self, obj):
        if not obj.image:
            return None
        return UploadedFileSerializer(obj.image, context=self.context).data


class GalleryGroupSerializer(serializers.ModelSerializer):
    images = GalleryImageSerializer(many=True, read_only=True)

    class Meta:
        model = GalleryGroup
        fields = ["id", "name", "images", "created_at"]

class CourseListByNavigationCourseSerializer(serializers.ModelSerializer):
    image = serializers.SerializerMethodField()
    banner = serializers.SerializerMethodField()

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

    def get_image(self, obj):
        if not obj.image:
            return None
        return UploadedFileSerializer(obj.image, context=self.context).data

    def get_banner(self, obj):
        if not obj.banner:
            return None
        return UploadedFileSerializer(obj.banner, context=self.context).data


class CoursesByNavigationSerializer(serializers.ModelSerializer):
    courses = serializers.SerializerMethodField()

    class Meta:
        model = Navigation
        fields = [
            "id",
            "name",
            "slug",
            "sort_order",
            "courses",
        ]

    def get_courses(self, obj):
        courses = obj.courses.all().order_by("sort_order", "created_at")
        return CourseListByNavigationCourseSerializer(
            courses,
            many=True,
            context=self.context,
        ).data

class CourseSearchSuggestionSerializer(serializers.ModelSerializer):
    navigation = serializers.SerializerMethodField()

    class Meta:
        model = Courses
        fields = [
            "id",
            "name",
            "slug",
            "navigation",
        ]

    def get_navigation(self, obj):
        if not obj.navigation:
            return None

        return {
            "id": obj.navigation.id,
            "name": obj.navigation.name,
            "slug": obj.navigation.slug,
        }