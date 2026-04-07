from __future__ import annotations

from drf_spectacular.utils import extend_schema, extend_schema_view
from rest_framework import mixins, status, viewsets, filters
from rest_framework.decorators import action
from rest_framework.response import Response

from common.permissions import IsSchoolManagement, IsAuthenticatedAndActive
from utils.get_school_id_by_token import get_school_for_user
from website.models import (Navigation, Courses, HomepageBanner, Icons, PrincipalMessage, Testimonial, Ads, Careers,
    AboutUs,
    Events,
    Blogs,
    FooterGroup,
    FooterLink,
    GalleryGroup,
    GalleryImage)
from website.serializers import (
    NavigationCreateSerializer,
    NavigationUpdateSerializer,
    NavigationReadSerializer,
    NavigationReorderSerializer,
    CoursesCreateSerializer,
    CoursesReadSerializer,
    CoursesReorderSerializer,
    CoursesUpdateSerializer,
    HomepageBannerCreateSerializer,
    HomepageBannerUpdateSerializer,
    HomepageBannerReadSerializer,
    HomepageBannerReorderSerializer,
    IconsCreateSerializer,
    IconsUpdateSerializer,
    IconsReadSerializer,
    IconsReorderSerializer,
    PrincipalMessageCreateSerializer,
    PrincipalMessageUpdateSerializer,
    PrincipalMessageReadSerializer,
    TestimonialCreateSerializer,
    TestimonialUpdateSerializer,
    TestimonialReadSerializer,
    AdsCreateSerializer,
    AdsUpdateSerializer,
    AdsReadSerializer,
    CareersCreateSerializer,
    CareersUpdateSerializer,
    CareersReadSerializer,
    AboutUsCreateSerializer,
    AboutUsUpdateSerializer,
    AboutUsReadSerializer,
    EventsCreateSerializer,
    EventsUpdateSerializer,
    EventsReadSerializer,
    BlogsCreateSerializer,
    BlogsUpdateSerializer,
    BlogsReadSerializer,
    FooterGroupCreateSerializer,
    FooterGroupUpdateSerializer,
    FooterGroupReadSerializer,
    FooterLinkCreateSerializer,
    FooterLinkUpdateSerializer,
    FooterLinkReadSerializer,
    GalleryGroupCreateSerializer,
    GalleryGroupUpdateSerializer,
    GalleryGroupReadSerializer,
    GalleryImageCreateSerializer,
    GalleryImageUpdateSerializer,
    GalleryImageReadSerializer,
)


@extend_schema_view(
    list=extend_schema(tags=["Navigation"]),
    create=extend_schema(tags=["Navigation"], request=NavigationCreateSerializer),
    retrieve=extend_schema(tags=["Navigation"]),
    update=extend_schema(tags=["Navigation"], request=NavigationUpdateSerializer),
    partial_update=extend_schema(tags=["Navigation"], request=NavigationUpdateSerializer),
    destroy=extend_schema(tags=["Navigation"]),
)
class NavigationViewSet(
    mixins.CreateModelMixin,
    mixins.ListModelMixin,
    mixins.RetrieveModelMixin,
    mixins.UpdateModelMixin,
    mixins.DestroyModelMixin,
    viewsets.GenericViewSet,
):
    permission_classes = [IsAuthenticatedAndActive, IsSchoolManagement]
    lookup_field = "pk"
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ["name", "slug"]
    ordering_fields = ["sort_order", "name", "created_at", "updated_at"]
    ordering = ["sort_order", "created_at"]

    def get_queryset(self):
        school = get_school_for_user(self.request.user)
        return (
            Navigation.objects
            .select_related("school", "created_by", "updated_by")
            .filter(school=school)
            .order_by("sort_order", "created_at")
        )

    def get_serializer_class(self):
        if self.action == "create":
            return NavigationCreateSerializer
        if self.action in ("update", "partial_update"):
            return NavigationUpdateSerializer
        return NavigationReadSerializer

    def create(self, request, *args, **kwargs):
        serializer = NavigationCreateSerializer(data=request.data, context={"request": request})
        print("Create Navigation - Request Data:", request.data)  # Debug log
        print("AccessToken User:", getattr(request, "user", None))  # Debug log
        serializer.is_valid(raise_exception=True)
        obj = serializer.save()
        return Response(
            {"message": "Navigation created.", "data": NavigationReadSerializer(obj).data},
            status=status.HTTP_201_CREATED,
        )

    def update(self, request, *args, **kwargs):
        obj = self.get_object()
        serializer = NavigationUpdateSerializer(
            instance=obj,
            data=request.data,
            partial=False,
            context={"request": request},
        )
        serializer.is_valid(raise_exception=True)
        obj = serializer.save()
        return Response({"message": "Navigation updated.", "data": NavigationReadSerializer(obj).data})

    def partial_update(self, request, *args, **kwargs):
        obj = self.get_object()
        serializer = NavigationUpdateSerializer(
            instance=obj,
            data=request.data,
            partial=True,
            context={"request": request},
        )
        serializer.is_valid(raise_exception=True)
        obj = serializer.save()
        return Response({"message": "Navigation updated.", "data": NavigationReadSerializer(obj).data})

    def destroy(self, request, *args, **kwargs):
        obj = self.get_object()
        obj.delete()
        return Response({"message": "Navigation deleted successfully."}, status=status.HTTP_200_OK)

    @extend_schema(tags=["Navigation"], request=NavigationReorderSerializer)
    @action(detail=False, methods=["post"], url_path="reorder")
    def reorder(self, request):
        serializer = NavigationReorderSerializer(data=request.data, context={"request": request})
        serializer.is_valid(raise_exception=True)
        result = serializer.save()
        return Response(
            {"message": "Navigations reordered.", "data": result},
            status=status.HTTP_200_OK,
        )

# ------------------------------------------------------------------------------
# Courses ViewSet
# ------------------------------------------------------------------------------
@extend_schema_view(
    list=extend_schema(tags=["Courses"]),
    create=extend_schema(tags=["Courses"], request=CoursesCreateSerializer),
    retrieve=extend_schema(tags=["Courses"]),
    update=extend_schema(tags=["Courses"], request=CoursesUpdateSerializer),
    partial_update=extend_schema(tags=["Courses"], request=CoursesUpdateSerializer),
    destroy=extend_schema(tags=["Courses"]),
)
class CoursesViewSet(
    mixins.CreateModelMixin,
    mixins.ListModelMixin,
    mixins.RetrieveModelMixin,
    mixins.UpdateModelMixin,
    mixins.DestroyModelMixin,
    viewsets.GenericViewSet,
):
    permission_classes = [IsAuthenticatedAndActive, IsSchoolManagement]
    lookup_field = "pk"
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ["name", "slug", "description", "tags"]
    ordering_fields = ["sort_order", "name", "created_at", "updated_at", "is_popular"]
    ordering = ["sort_order", "created_at"]

    def get_queryset(self):
        school = get_school_for_user(self.request.user)
        return (
            Courses.objects
            .select_related(
                "school",
                "navigation",
                "image",
                "banner",
                "created_by",
                "updated_by",
            )
            .filter(school=school)
            .order_by("sort_order", "created_at")
        )

    def get_serializer_class(self):
        if self.action == "create":
            return CoursesCreateSerializer
        if self.action in ("update", "partial_update"):
            return CoursesUpdateSerializer
        return CoursesReadSerializer

    def create(self, request, *args, **kwargs):
        serializer = CoursesCreateSerializer(data=request.data, context={"request": request})
        serializer.is_valid(raise_exception=True)
        obj = serializer.save()
        return Response(
            {"message": "Course created.", "data": CoursesReadSerializer(obj).data},
            status=status.HTTP_201_CREATED,
        )

    def update(self, request, *args, **kwargs):
        obj = self.get_object()
        serializer = CoursesUpdateSerializer(
            instance=obj,
            data=request.data,
            partial=False,
            context={"request": request},
        )
        serializer.is_valid(raise_exception=True)
        obj = serializer.save()
        return Response({"message": "Course updated.", "data": CoursesReadSerializer(obj).data})

    def partial_update(self, request, *args, **kwargs):
        obj = self.get_object()
        serializer = CoursesUpdateSerializer(
            instance=obj,
            data=request.data,
            partial=True,
            context={"request": request},
        )
        serializer.is_valid(raise_exception=True)
        obj = serializer.save()
        return Response({"message": "Course updated.", "data": CoursesReadSerializer(obj).data})

    def destroy(self, request, *args, **kwargs):
        obj = self.get_object()
        obj.delete()
        return Response({"message": "Course deleted successfully."}, status=status.HTTP_200_OK)

    @extend_schema(tags=["Courses"], request=CoursesReorderSerializer)
    @action(detail=False, methods=["post"], url_path="reorder")
    def reorder(self, request):
        serializer = CoursesReorderSerializer(data=request.data, context={"request": request})
        serializer.is_valid(raise_exception=True)
        result = serializer.save()
        return Response(
            {"message": "Courses reordered.", "data": result},
            status=status.HTTP_200_OK,
        )

# ------------------------------------
# Homepage Viewset
# ------------------------------------
@extend_schema_view(
    list=extend_schema(tags=["Homepage Banner"]),
    create=extend_schema(tags=["Homepage Banner"], request=HomepageBannerCreateSerializer),
    retrieve=extend_schema(tags=["Homepage Banner"]),
    update=extend_schema(tags=["Homepage Banner"], request=HomepageBannerUpdateSerializer),
    partial_update=extend_schema(tags=["Homepage Banner"], request=HomepageBannerUpdateSerializer),
    destroy=extend_schema(tags=["Homepage Banner"]),
)
class HomepageBannerViewSet(
    mixins.CreateModelMixin,
    mixins.ListModelMixin,
    mixins.RetrieveModelMixin,
    mixins.UpdateModelMixin,
    mixins.DestroyModelMixin,
    viewsets.GenericViewSet,
):
    permission_classes = [IsAuthenticatedAndActive, IsSchoolManagement]
    lookup_field = "pk"
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ["title", "subtitle", "description", "button_link", "link_url"]
    ordering_fields = ["sort_order", "title", "created_at", "updated_at"]
    ordering = ["sort_order", "created_at"]

    def get_queryset(self):
        school = get_school_for_user(self.request.user)
        return (
            HomepageBanner.objects
            .select_related("school", "image", "created_by", "updated_by")
            .filter(school=school)
            .order_by("sort_order", "created_at")
        )

    def get_serializer_class(self):
        if self.action == "create":
            return HomepageBannerCreateSerializer
        if self.action in ("update", "partial_update"):
            return HomepageBannerUpdateSerializer
        return HomepageBannerReadSerializer

    def create(self, request, *args, **kwargs):
        serializer = HomepageBannerCreateSerializer(data=request.data, context={"request": request})
        serializer.is_valid(raise_exception=True)
        obj = serializer.save()
        return Response(
            {"message": "Homepage banner created.", "data": HomepageBannerReadSerializer(obj).data},
            status=status.HTTP_201_CREATED,
        )

    def update(self, request, *args, **kwargs):
        obj = self.get_object()
        serializer = HomepageBannerUpdateSerializer(
            instance=obj,
            data=request.data,
            partial=False,
            context={"request": request},
        )
        serializer.is_valid(raise_exception=True)
        obj = serializer.save()
        return Response({"message": "Homepage banner updated.", "data": HomepageBannerReadSerializer(obj).data})

    def partial_update(self, request, *args, **kwargs):
        obj = self.get_object()
        serializer = HomepageBannerUpdateSerializer(
            instance=obj,
            data=request.data,
            partial=True,
            context={"request": request},
        )
        serializer.is_valid(raise_exception=True)
        obj = serializer.save()
        return Response({"message": "Homepage banner updated.", "data": HomepageBannerReadSerializer(obj).data})

    def destroy(self, request, *args, **kwargs):
        obj = self.get_object()
        obj.delete()
        return Response({"message": "Homepage banner deleted successfully."}, status=status.HTTP_200_OK)

    @extend_schema(tags=["Homepage Banner"], request=HomepageBannerReorderSerializer)
    @action(detail=False, methods=["post"], url_path="reorder")
    def reorder(self, request):
        serializer = HomepageBannerReorderSerializer(data=request.data, context={"request": request})
        serializer.is_valid(raise_exception=True)
        result = serializer.save()
        return Response(
            {"message": "Homepage banners reordered.", "data": result},
            status=status.HTTP_200_OK,
        )

# -------------------------------
# Icons Viewset
# -------------------------------
@extend_schema_view(
    list=extend_schema(tags=["Icons"]),
    create=extend_schema(tags=["Icons"], request=IconsCreateSerializer),
    retrieve=extend_schema(tags=["Icons"]),
    update=extend_schema(tags=["Icons"], request=IconsUpdateSerializer),
    partial_update=extend_schema(tags=["Icons"], request=IconsUpdateSerializer),
    destroy=extend_schema(tags=["Icons"]),
)
class IconsViewSet(
    mixins.CreateModelMixin,
    mixins.ListModelMixin,
    mixins.RetrieveModelMixin,
    mixins.UpdateModelMixin,
    mixins.DestroyModelMixin,
    viewsets.GenericViewSet,
):
    permission_classes = [IsAuthenticatedAndActive, IsSchoolManagement]
    lookup_field = "pk"
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ["name"]
    ordering_fields = ["sort_order", "name", "created_at", "updated_at"]
    ordering = ["sort_order", "created_at"]

    def get_queryset(self):
        school = get_school_for_user(self.request.user)
        return (
            Icons.objects
            .select_related("school", "image", "created_by", "updated_by")
            .filter(school=school)
            .order_by("sort_order", "created_at")
        )

    def get_serializer_class(self):
        if self.action == "create":
            return IconsCreateSerializer
        if self.action in ("update", "partial_update"):
            return IconsUpdateSerializer
        return IconsReadSerializer

    def create(self, request, *args, **kwargs):
        serializer = IconsCreateSerializer(data=request.data, context={"request": request})
        serializer.is_valid(raise_exception=True)
        obj = serializer.save()
        return Response(
            {"message": "Icon created.", "data": IconsReadSerializer(obj).data},
            status=status.HTTP_201_CREATED,
        )

    def update(self, request, *args, **kwargs):
        obj = self.get_object()
        serializer = IconsUpdateSerializer(instance=obj, data=request.data, partial=False, context={"request": request})
        serializer.is_valid(raise_exception=True)
        obj = serializer.save()
        return Response({"message": "Icon updated.", "data": IconsReadSerializer(obj).data})

    def partial_update(self, request, *args, **kwargs):
        obj = self.get_object()
        serializer = IconsUpdateSerializer(instance=obj, data=request.data, partial=True, context={"request": request})
        serializer.is_valid(raise_exception=True)
        obj = serializer.save()
        return Response({"message": "Icon updated.", "data": IconsReadSerializer(obj).data})

    def destroy(self, request, *args, **kwargs):
        obj = self.get_object()
        obj.delete()
        return Response({"message": "Icon deleted successfully."}, status=status.HTTP_200_OK)

    @extend_schema(tags=["Icons"], request=IconsReorderSerializer)
    @action(detail=False, methods=["post"], url_path="reorder")
    def reorder(self, request):
        serializer = IconsReorderSerializer(data=request.data, context={"request": request})
        serializer.is_valid(raise_exception=True)
        result = serializer.save()
        return Response({"message": "Icons reordered.", "data": result}, status=status.HTTP_200_OK)


# --------------------------------------
# Principal Message Viewset
# --------------------------------------
@extend_schema_view(
    list=extend_schema(tags=["Principal Message"]),
    create=extend_schema(tags=["Principal Message"], request=PrincipalMessageCreateSerializer),
    retrieve=extend_schema(tags=["Principal Message"]),
    update=extend_schema(tags=["Principal Message"], request=PrincipalMessageUpdateSerializer),
    partial_update=extend_schema(tags=["Principal Message"], request=PrincipalMessageUpdateSerializer),
    destroy=extend_schema(tags=["Principal Message"]),
)
class PrincipalMessageViewSet(
    mixins.CreateModelMixin,
    mixins.ListModelMixin,
    mixins.RetrieveModelMixin,
    mixins.UpdateModelMixin,
    mixins.DestroyModelMixin,
    viewsets.GenericViewSet,
):
    permission_classes = [IsAuthenticatedAndActive, IsSchoolManagement]
    lookup_field = "pk"
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ["title", "message"]
    ordering_fields = ["title", "created_at", "updated_at"]
    ordering = ["-created_at"]

    def get_queryset(self):
        school = get_school_for_user(self.request.user)
        return (
            PrincipalMessage.objects
            .select_related("school", "image", "created_by", "updated_by")
            .filter(school=school)
            .order_by("-created_at")
        )

    def get_serializer_class(self):
        if self.action == "create":
            return PrincipalMessageCreateSerializer
        if self.action in ("update", "partial_update"):
            return PrincipalMessageUpdateSerializer
        return PrincipalMessageReadSerializer

    def create(self, request, *args, **kwargs):
        serializer = PrincipalMessageCreateSerializer(data=request.data, context={"request": request})
        serializer.is_valid(raise_exception=True)
        obj = serializer.save()
        return Response(
            {"message": "Principal message created.", "data": PrincipalMessageReadSerializer(obj).data},
            status=status.HTTP_201_CREATED,
        )

    def update(self, request, *args, **kwargs):
        obj = self.get_object()
        serializer = PrincipalMessageUpdateSerializer(
            instance=obj,
            data=request.data,
            partial=False,
            context={"request": request},
        )
        serializer.is_valid(raise_exception=True)
        obj = serializer.save()
        return Response({"message": "Principal message updated.", "data": PrincipalMessageReadSerializer(obj).data})

    def partial_update(self, request, *args, **kwargs):
        obj = self.get_object()
        serializer = PrincipalMessageUpdateSerializer(
            instance=obj,
            data=request.data,
            partial=True,
            context={"request": request},
        )
        serializer.is_valid(raise_exception=True)
        obj = serializer.save()
        return Response({"message": "Principal message updated.", "data": PrincipalMessageReadSerializer(obj).data})

    def destroy(self, request, *args, **kwargs):
        obj = self.get_object()
        obj.delete()
        return Response({"message": "Principal message deleted successfully."}, status=status.HTTP_200_OK)

# --------------------------------------
# Testimonial Viewset
# --------------------------------------
@extend_schema_view(
    list=extend_schema(tags=["Testimonial"]),
    create=extend_schema(tags=["Testimonial"], request=TestimonialCreateSerializer),
    retrieve=extend_schema(tags=["Testimonial"]),
    update=extend_schema(tags=["Testimonial"], request=TestimonialUpdateSerializer),
    partial_update=extend_schema(tags=["Testimonial"], request=TestimonialUpdateSerializer),
    destroy=extend_schema(tags=["Testimonial"]),
)
class TestimonialViewSet(
    mixins.CreateModelMixin,
    mixins.ListModelMixin,
    mixins.RetrieveModelMixin,
    mixins.UpdateModelMixin,
    mixins.DestroyModelMixin,
    viewsets.GenericViewSet,
):
    permission_classes = [IsAuthenticatedAndActive, IsSchoolManagement]
    lookup_field = "pk"
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ["name", "role", "message"]
    ordering_fields = ["name", "created_at", "updated_at"]
    ordering = ["-created_at"]

    def get_queryset(self):
        school = get_school_for_user(self.request.user)
        return (
            Testimonial.objects
            .select_related("school", "image", "created_by", "updated_by")
            .filter(school=school)
            .order_by("-created_at")
        )

    def get_serializer_class(self):
        if self.action == "create":
            return TestimonialCreateSerializer
        if self.action in ("update", "partial_update"):
            return TestimonialUpdateSerializer
        return TestimonialReadSerializer

    def create(self, request, *args, **kwargs):
        serializer = TestimonialCreateSerializer(data=request.data, context={"request": request})
        serializer.is_valid(raise_exception=True)
        obj = serializer.save()
        return Response(
            {"message": "Testimonial created.", "data": TestimonialReadSerializer(obj).data},
            status=status.HTTP_201_CREATED,
        )

    def update(self, request, *args, **kwargs):
        obj = self.get_object()
        serializer = TestimonialUpdateSerializer(
            instance=obj,
            data=request.data,
            partial=False,
            context={"request": request},
        )
        serializer.is_valid(raise_exception=True)
        obj = serializer.save()
        return Response({"message": "Testimonial updated.", "data": TestimonialReadSerializer(obj).data})

    def partial_update(self, request, *args, **kwargs):
        obj = self.get_object()
        serializer = TestimonialUpdateSerializer(
            instance=obj,
            data=request.data,
            partial=True,
            context={"request": request},
        )
        serializer.is_valid(raise_exception=True)
        obj = serializer.save()
        return Response({"message": "Testimonial updated.", "data": TestimonialReadSerializer(obj).data})

    def destroy(self, request, *args, **kwargs):
        obj = self.get_object()
        obj.delete()
        return Response({"message": "Testimonial deleted successfully."}, status=status.HTTP_200_OK)


# --------------------------------------
# Ads Viewset
# --------------------------------------
@extend_schema_view(
    list=extend_schema(tags=["Testimonial"]),
    create=extend_schema(tags=["Testimonial"], request=TestimonialCreateSerializer),
    retrieve=extend_schema(tags=["Testimonial"]),
    update=extend_schema(tags=["Testimonial"], request=TestimonialUpdateSerializer),
    partial_update=extend_schema(tags=["Testimonial"], request=TestimonialUpdateSerializer),
    destroy=extend_schema(tags=["Testimonial"]),
)
class TestimonialViewSet(
    mixins.CreateModelMixin,
    mixins.ListModelMixin,
    mixins.RetrieveModelMixin,
    mixins.UpdateModelMixin,
    mixins.DestroyModelMixin,
    viewsets.GenericViewSet,
):
    permission_classes = [IsAuthenticatedAndActive, IsSchoolManagement]
    lookup_field = "pk"
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ["name", "role", "message"]
    ordering_fields = ["name", "created_at", "updated_at"]
    ordering = ["-created_at"]

    def get_queryset(self):
        school = get_school_for_user(self.request.user)
        return (
            Testimonial.objects
            .select_related("school", "image", "created_by", "updated_by")
            .filter(school=school)
            .order_by("-created_at")
        )

    def get_serializer_class(self):
        if self.action == "create":
            return TestimonialCreateSerializer
        if self.action in ("update", "partial_update"):
            return TestimonialUpdateSerializer
        return TestimonialReadSerializer

    def create(self, request, *args, **kwargs):
        serializer = TestimonialCreateSerializer(data=request.data, context={"request": request})
        serializer.is_valid(raise_exception=True)
        obj = serializer.save()
        return Response(
            {"message": "Testimonial created.", "data": TestimonialReadSerializer(obj).data},
            status=status.HTTP_201_CREATED,
        )

    def update(self, request, *args, **kwargs):
        obj = self.get_object()
        serializer = TestimonialUpdateSerializer(
            instance=obj,
            data=request.data,
            partial=False,
            context={"request": request},
        )
        serializer.is_valid(raise_exception=True)
        obj = serializer.save()
        return Response({"message": "Testimonial updated.", "data": TestimonialReadSerializer(obj).data})

    def partial_update(self, request, *args, **kwargs):
        obj = self.get_object()
        serializer = TestimonialUpdateSerializer(
            instance=obj,
            data=request.data,
            partial=True,
            context={"request": request},
        )
        serializer.is_valid(raise_exception=True)
        obj = serializer.save()
        return Response({"message": "Testimonial updated.", "data": TestimonialReadSerializer(obj).data})

    def destroy(self, request, *args, **kwargs):
        obj = self.get_object()
        obj.delete()
        return Response({"message": "Testimonial deleted successfully."}, status=status.HTTP_200_OK)

# --------------------------------------
# Ads Viewset
# --------------------------------------
@extend_schema_view(
    list=extend_schema(tags=["Ads"]),
    create=extend_schema(tags=["Ads"], request=AdsCreateSerializer),
    retrieve=extend_schema(tags=["Ads"]),
    update=extend_schema(tags=["Ads"], request=AdsUpdateSerializer),
    partial_update=extend_schema(tags=["Ads"], request=AdsUpdateSerializer),
    destroy=extend_schema(tags=["Ads"]),
)
class AdsViewSet(
    mixins.CreateModelMixin,
    mixins.ListModelMixin,
    mixins.RetrieveModelMixin,
    mixins.UpdateModelMixin,
    mixins.DestroyModelMixin,
    viewsets.GenericViewSet,
):
    permission_classes = [IsAuthenticatedAndActive, IsSchoolManagement]
    lookup_field = "pk"
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ["title", "description", "link_url"]
    ordering_fields = ["title", "created_at", "updated_at"]
    ordering = ["-created_at"]

    def get_queryset(self):
        school = get_school_for_user(self.request.user)
        return (
            Ads.objects
            .select_related("school", "image", "created_by", "updated_by")
            .filter(school=school)
            .order_by("-created_at")
        )

    def get_serializer_class(self):
        if self.action == "create":
            return AdsCreateSerializer
        if self.action in ("update", "partial_update"):
            return AdsUpdateSerializer
        return AdsReadSerializer

    def create(self, request, *args, **kwargs):
        serializer = AdsCreateSerializer(data=request.data, context={"request": request})
        serializer.is_valid(raise_exception=True)
        obj = serializer.save()
        return Response(
            {"message": "Ad created.", "data": AdsReadSerializer(obj).data},
            status=status.HTTP_201_CREATED,
        )

    def update(self, request, *args, **kwargs):
        obj = self.get_object()
        serializer = AdsUpdateSerializer(
            instance=obj,
            data=request.data,
            partial=False,
            context={"request": request},
        )
        serializer.is_valid(raise_exception=True)
        obj = serializer.save()
        return Response({"message": "Ad updated.", "data": AdsReadSerializer(obj).data})

    def partial_update(self, request, *args, **kwargs):
        obj = self.get_object()
        serializer = AdsUpdateSerializer(
            instance=obj,
            data=request.data,
            partial=True,
            context={"request": request},
        )
        serializer.is_valid(raise_exception=True)
        obj = serializer.save()
        return Response({"message": "Ad updated.", "data": AdsReadSerializer(obj).data})

    def destroy(self, request, *args, **kwargs):
        obj = self.get_object()
        obj.delete()
        return Response({"message": "Ad deleted successfully."}, status=status.HTTP_200_OK)


@extend_schema_view(
    list=extend_schema(tags=["Careers"]),
    create=extend_schema(tags=["Careers"], request=CareersCreateSerializer),
    retrieve=extend_schema(tags=["Careers"]),
    update=extend_schema(tags=["Careers"], request=CareersUpdateSerializer),
    partial_update=extend_schema(tags=["Careers"], request=CareersUpdateSerializer),
    destroy=extend_schema(tags=["Careers"]),
)
class CareersViewSet(
    mixins.CreateModelMixin,
    mixins.ListModelMixin,
    mixins.RetrieveModelMixin,
    mixins.UpdateModelMixin,
    mixins.DestroyModelMixin,
    viewsets.GenericViewSet,
):
    permission_classes = [IsAuthenticatedAndActive, IsSchoolManagement]
    lookup_field = "pk"
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ["title", "position", "job_description", "requirements"]
    ordering_fields = ["title", "expires_at", "created_at", "updated_at"]
    ordering = ["-created_at"]

    def get_queryset(self):
        school = get_school_for_user(self.request.user)
        return (
            Careers.objects
            .select_related("school", "created_by", "updated_by")
            .filter(school=school)
            .order_by("-created_at")
        )

    def get_serializer_class(self):
        if self.action == "create":
            return CareersCreateSerializer
        if self.action in ("update", "partial_update"):
            return CareersUpdateSerializer
        return CareersReadSerializer

    def create(self, request, *args, **kwargs):
        serializer = CareersCreateSerializer(data=request.data, context={"request": request})
        serializer.is_valid(raise_exception=True)
        obj = serializer.save()
        return Response({"message": "Career created.", "data": CareersReadSerializer(obj).data}, status=status.HTTP_201_CREATED)

    def update(self, request, *args, **kwargs):
        obj = self.get_object()
        serializer = CareersUpdateSerializer(instance=obj, data=request.data, partial=False, context={"request": request})
        serializer.is_valid(raise_exception=True)
        obj = serializer.save()
        return Response({"message": "Career updated.", "data": CareersReadSerializer(obj).data})

    def partial_update(self, request, *args, **kwargs):
        obj = self.get_object()
        serializer = CareersUpdateSerializer(instance=obj, data=request.data, partial=True, context={"request": request})
        serializer.is_valid(raise_exception=True)
        obj = serializer.save()
        return Response({"message": "Career updated.", "data": CareersReadSerializer(obj).data})

    def destroy(self, request, *args, **kwargs):
        obj = self.get_object()
        obj.delete()
        return Response({"message": "Career deleted successfully."}, status=status.HTTP_200_OK)

@extend_schema_view(
    list=extend_schema(tags=["Careers"]),
    create=extend_schema(tags=["Careers"], request=CareersCreateSerializer),
    retrieve=extend_schema(tags=["Careers"]),
    update=extend_schema(tags=["Careers"], request=CareersUpdateSerializer),
    partial_update=extend_schema(tags=["Careers"], request=CareersUpdateSerializer),
    destroy=extend_schema(tags=["Careers"]),
)
class CareersViewSet(
    mixins.CreateModelMixin,
    mixins.ListModelMixin,
    mixins.RetrieveModelMixin,
    mixins.UpdateModelMixin,
    mixins.DestroyModelMixin,
    viewsets.GenericViewSet,
):
    permission_classes = [IsAuthenticatedAndActive, IsSchoolManagement]
    lookup_field = "pk"
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ["title", "position", "job_description", "requirements"]
    ordering_fields = ["title", "expires_at", "created_at", "updated_at"]
    ordering = ["-created_at"]

    def get_queryset(self):
        school = get_school_for_user(self.request.user)
        return (
            Careers.objects
            .select_related("school", "created_by", "updated_by")
            .filter(school=school)
            .order_by("-created_at")
        )

    def get_serializer_class(self):
        if self.action == "create":
            return CareersCreateSerializer
        if self.action in ("update", "partial_update"):
            return CareersUpdateSerializer
        return CareersReadSerializer

    def create(self, request, *args, **kwargs):
        serializer = CareersCreateSerializer(data=request.data, context={"request": request})
        serializer.is_valid(raise_exception=True)
        obj = serializer.save()
        return Response({"message": "Career created.", "data": CareersReadSerializer(obj).data}, status=status.HTTP_201_CREATED)

    def update(self, request, *args, **kwargs):
        obj = self.get_object()
        serializer = CareersUpdateSerializer(instance=obj, data=request.data, partial=False, context={"request": request})
        serializer.is_valid(raise_exception=True)
        obj = serializer.save()
        return Response({"message": "Career updated.", "data": CareersReadSerializer(obj).data})

    def partial_update(self, request, *args, **kwargs):
        obj = self.get_object()
        serializer = CareersUpdateSerializer(instance=obj, data=request.data, partial=True, context={"request": request})
        serializer.is_valid(raise_exception=True)
        obj = serializer.save()
        return Response({"message": "Career updated.", "data": CareersReadSerializer(obj).data})

    def destroy(self, request, *args, **kwargs):
        obj = self.get_object()
        obj.delete()
        return Response({"message": "Career deleted successfully."}, status=status.HTTP_200_OK)


@extend_schema_view(
    list=extend_schema(tags=["About Us"]),
    create=extend_schema(tags=["About Us"], request=AboutUsCreateSerializer),
    retrieve=extend_schema(tags=["About Us"]),
    update=extend_schema(tags=["About Us"], request=AboutUsUpdateSerializer),
    partial_update=extend_schema(tags=["About Us"], request=AboutUsUpdateSerializer),
    destroy=extend_schema(tags=["About Us"]),
)
class AboutUsViewSet(
    mixins.CreateModelMixin,
    mixins.ListModelMixin,
    mixins.RetrieveModelMixin,
    mixins.UpdateModelMixin,
    mixins.DestroyModelMixin,
    viewsets.GenericViewSet,
):
    permission_classes = [IsAuthenticatedAndActive, IsSchoolManagement]
    lookup_field = "pk"
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ["title", "description"]
    ordering_fields = ["title", "created_at", "updated_at"]
    ordering = ["-created_at"]

    def get_queryset(self):
        school = get_school_for_user(self.request.user)
        return (
            AboutUs.objects
            .select_related("school", "image", "created_by", "updated_by")
            .filter(school=school)
            .order_by("-created_at")
        )

    def get_serializer_class(self):
        if self.action == "create":
            return AboutUsCreateSerializer
        if self.action in ("update", "partial_update"):
            return AboutUsUpdateSerializer
        return AboutUsReadSerializer

    def create(self, request, *args, **kwargs):
        serializer = AboutUsCreateSerializer(data=request.data, context={"request": request})
        serializer.is_valid(raise_exception=True)
        obj = serializer.save()
        return Response({"message": "About us section created.", "data": AboutUsReadSerializer(obj).data}, status=status.HTTP_201_CREATED)

    def update(self, request, *args, **kwargs):
        obj = self.get_object()
        serializer = AboutUsUpdateSerializer(instance=obj, data=request.data, partial=False, context={"request": request})
        serializer.is_valid(raise_exception=True)
        obj = serializer.save()
        return Response({"message": "About us section updated.", "data": AboutUsReadSerializer(obj).data})

    def partial_update(self, request, *args, **kwargs):
        obj = self.get_object()
        serializer = AboutUsUpdateSerializer(instance=obj, data=request.data, partial=True, context={"request": request})
        serializer.is_valid(raise_exception=True)
        obj = serializer.save()
        return Response({"message": "About us section updated.", "data": AboutUsReadSerializer(obj).data})

    def destroy(self, request, *args, **kwargs):
        obj = self.get_object()
        obj.delete()
        return Response({"message": "About us section deleted successfully."}, status=status.HTTP_200_OK)


@extend_schema_view(
    list=extend_schema(tags=["Events"]),
    create=extend_schema(tags=["Events"], request=EventsCreateSerializer),
    retrieve=extend_schema(tags=["Events"]),
    update=extend_schema(tags=["Events"], request=EventsUpdateSerializer),
    partial_update=extend_schema(tags=["Events"], request=EventsUpdateSerializer),
    destroy=extend_schema(tags=["Events"]),
)
class EventsViewSet(
    mixins.CreateModelMixin,
    mixins.ListModelMixin,
    mixins.RetrieveModelMixin,
    mixins.UpdateModelMixin,
    mixins.DestroyModelMixin,
    viewsets.GenericViewSet,
):
    permission_classes = [IsAuthenticatedAndActive, IsSchoolManagement]
    lookup_field = "pk"
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ["title", "description"]
    ordering_fields = ["title", "event_date", "created_at", "updated_at"]
    ordering = ["-created_at"]

    def get_queryset(self):
        return (
            Events.objects
            .select_related("created_by", "updated_by")
            .order_by("-created_at")
        )

    def get_serializer_class(self):
        if self.action == "create":
            return EventsCreateSerializer
        if self.action in ("update", "partial_update"):
            return EventsUpdateSerializer
        return EventsReadSerializer

    def create(self, request, *args, **kwargs):
        serializer = EventsCreateSerializer(data=request.data, context={"request": request})
        serializer.is_valid(raise_exception=True)
        obj = serializer.save()
        return Response({"message": "Event created.", "data": EventsReadSerializer(obj).data}, status=status.HTTP_201_CREATED)

    def update(self, request, *args, **kwargs):
        obj = self.get_object()
        serializer = EventsUpdateSerializer(instance=obj, data=request.data, partial=False, context={"request": request})
        serializer.is_valid(raise_exception=True)
        obj = serializer.save()
        return Response({"message": "Event updated.", "data": EventsReadSerializer(obj).data})

    def partial_update(self, request, *args, **kwargs):
        obj = self.get_object()
        serializer = EventsUpdateSerializer(instance=obj, data=request.data, partial=True, context={"request": request})
        serializer.is_valid(raise_exception=True)
        obj = serializer.save()
        return Response({"message": "Event updated.", "data": EventsReadSerializer(obj).data})

    def destroy(self, request, *args, **kwargs):
        obj = self.get_object()
        obj.delete()
        return Response({"message": "Event deleted successfully."}, status=status.HTTP_200_OK)


@extend_schema_view(
    list=extend_schema(tags=["Blogs"]),
    create=extend_schema(tags=["Blogs"], request=BlogsCreateSerializer),
    retrieve=extend_schema(tags=["Blogs"]),
    update=extend_schema(tags=["Blogs"], request=BlogsUpdateSerializer),
    partial_update=extend_schema(tags=["Blogs"], request=BlogsUpdateSerializer),
    destroy=extend_schema(tags=["Blogs"]),
)
class BlogsViewSet(
    mixins.CreateModelMixin,
    mixins.ListModelMixin,
    mixins.RetrieveModelMixin,
    mixins.UpdateModelMixin,
    mixins.DestroyModelMixin,
    viewsets.GenericViewSet,
):
    permission_classes = [IsAuthenticatedAndActive, IsSchoolManagement]
    lookup_field = "pk"
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ["title", "content", "author"]
    ordering_fields = ["title", "published_at", "created_at", "updated_at"]
    ordering = ["-created_at"]

    def get_queryset(self):
        return (
            Blogs.objects
            .select_related("created_by", "updated_by")
            .order_by("-created_at")
        )

    def get_serializer_class(self):
        if self.action == "create":
            return BlogsCreateSerializer
        if self.action in ("update", "partial_update"):
            return BlogsUpdateSerializer
        return BlogsReadSerializer

    def create(self, request, *args, **kwargs):
        serializer = BlogsCreateSerializer(data=request.data, context={"request": request})
        serializer.is_valid(raise_exception=True)
        obj = serializer.save()
        return Response({"message": "Blog created.", "data": BlogsReadSerializer(obj).data}, status=status.HTTP_201_CREATED)

    def update(self, request, *args, **kwargs):
        obj = self.get_object()
        serializer = BlogsUpdateSerializer(instance=obj, data=request.data, partial=False, context={"request": request})
        serializer.is_valid(raise_exception=True)
        obj = serializer.save()
        return Response({"message": "Blog updated.", "data": BlogsReadSerializer(obj).data})

    def partial_update(self, request, *args, **kwargs):
        obj = self.get_object()
        serializer = BlogsUpdateSerializer(instance=obj, data=request.data, partial=True, context={"request": request})
        serializer.is_valid(raise_exception=True)
        obj = serializer.save()
        return Response({"message": "Blog updated.", "data": BlogsReadSerializer(obj).data})

    def destroy(self, request, *args, **kwargs):
        obj = self.get_object()
        obj.delete()
        return Response({"message": "Blog deleted successfully."}, status=status.HTTP_200_OK)


@extend_schema_view(
    list=extend_schema(tags=["Footer Group"]),
    create=extend_schema(tags=["Footer Group"], request=FooterGroupCreateSerializer),
    retrieve=extend_schema(tags=["Footer Group"]),
    update=extend_schema(tags=["Footer Group"], request=FooterGroupUpdateSerializer),
    partial_update=extend_schema(tags=["Footer Group"], request=FooterGroupUpdateSerializer),
    destroy=extend_schema(tags=["Footer Group"]),
)
class FooterGroupViewSet(
    mixins.CreateModelMixin,
    mixins.ListModelMixin,
    mixins.RetrieveModelMixin,
    mixins.UpdateModelMixin,
    mixins.DestroyModelMixin,
    viewsets.GenericViewSet,
):
    permission_classes = [IsAuthenticatedAndActive, IsSchoolManagement]
    lookup_field = "pk"
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ["name"]
    ordering_fields = ["name", "created_at", "updated_at"]
    ordering = ["-created_at"]

    def get_queryset(self):
        school = get_school_for_user(self.request.user)
        return (
            FooterGroup.objects
            .select_related("school", "created_by", "updated_by")
            .filter(school=school)
            .order_by("-created_at")
        )

    def get_serializer_class(self):
        if self.action == "create":
            return FooterGroupCreateSerializer
        if self.action in ("update", "partial_update"):
            return FooterGroupUpdateSerializer
        return FooterGroupReadSerializer

    def create(self, request, *args, **kwargs):
        serializer = FooterGroupCreateSerializer(data=request.data, context={"request": request})
        serializer.is_valid(raise_exception=True)
        obj = serializer.save()
        return Response({"message": "Footer group created.", "data": FooterGroupReadSerializer(obj).data}, status=status.HTTP_201_CREATED)

    def update(self, request, *args, **kwargs):
        obj = self.get_object()
        serializer = FooterGroupUpdateSerializer(instance=obj, data=request.data, partial=False, context={"request": request})
        serializer.is_valid(raise_exception=True)
        obj = serializer.save()
        return Response({"message": "Footer group updated.", "data": FooterGroupReadSerializer(obj).data})

    def partial_update(self, request, *args, **kwargs):
        obj = self.get_object()
        serializer = FooterGroupUpdateSerializer(instance=obj, data=request.data, partial=True, context={"request": request})
        serializer.is_valid(raise_exception=True)
        obj = serializer.save()
        return Response({"message": "Footer group updated.", "data": FooterGroupReadSerializer(obj).data})

    def destroy(self, request, *args, **kwargs):
        obj = self.get_object()
        obj.delete()
        return Response({"message": "Footer group deleted successfully."}, status=status.HTTP_200_OK)


@extend_schema_view(
    list=extend_schema(tags=["Footer Link"]),
    create=extend_schema(tags=["Footer Link"], request=FooterLinkCreateSerializer),
    retrieve=extend_schema(tags=["Footer Link"]),
    update=extend_schema(tags=["Footer Link"], request=FooterLinkUpdateSerializer),
    partial_update=extend_schema(tags=["Footer Link"], request=FooterLinkUpdateSerializer),
    destroy=extend_schema(tags=["Footer Link"]),
)
class FooterLinkViewSet(
    mixins.CreateModelMixin,
    mixins.ListModelMixin,
    mixins.RetrieveModelMixin,
    mixins.UpdateModelMixin,
    mixins.DestroyModelMixin,
    viewsets.GenericViewSet,
):
    permission_classes = [IsAuthenticatedAndActive, IsSchoolManagement]
    lookup_field = "pk"
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ["name", "url", "footer_group__name"]
    ordering_fields = ["name", "created_at", "updated_at"]
    ordering = ["-created_at"]

    def get_queryset(self):
        school = get_school_for_user(self.request.user)
        return (
            FooterLink.objects
            .select_related("footer_group", "created_by", "updated_by")
            .filter(footer_group__school=school)
            .order_by("-created_at")
        )

    def get_serializer_class(self):
        if self.action == "create":
            return FooterLinkCreateSerializer
        if self.action in ("update", "partial_update"):
            return FooterLinkUpdateSerializer
        return FooterLinkReadSerializer

    def create(self, request, *args, **kwargs):
        serializer = FooterLinkCreateSerializer(data=request.data, context={"request": request})
        serializer.is_valid(raise_exception=True)
        obj = serializer.save()
        return Response({"message": "Footer link created.", "data": FooterLinkReadSerializer(obj).data}, status=status.HTTP_201_CREATED)

    def update(self, request, *args, **kwargs):
        obj = self.get_object()
        serializer = FooterLinkUpdateSerializer(instance=obj, data=request.data, partial=False, context={"request": request})
        serializer.is_valid(raise_exception=True)
        obj = serializer.save()
        return Response({"message": "Footer link updated.", "data": FooterLinkReadSerializer(obj).data})

    def partial_update(self, request, *args, **kwargs):
        obj = self.get_object()
        serializer = FooterLinkUpdateSerializer(instance=obj, data=request.data, partial=True, context={"request": request})
        serializer.is_valid(raise_exception=True)
        obj = serializer.save()
        return Response({"message": "Footer link updated.", "data": FooterLinkReadSerializer(obj).data})

    def destroy(self, request, *args, **kwargs):
        obj = self.get_object()
        obj.delete()
        return Response({"message": "Footer link deleted successfully."}, status=status.HTTP_200_OK)

@extend_schema_view(
    list=extend_schema(tags=["Gallery Group"]),
    create=extend_schema(tags=["Gallery Group"], request=GalleryGroupCreateSerializer),
    retrieve=extend_schema(tags=["Gallery Group"]),
    update=extend_schema(tags=["Gallery Group"], request=GalleryGroupUpdateSerializer),
    partial_update=extend_schema(tags=["Gallery Group"], request=GalleryGroupUpdateSerializer),
    destroy=extend_schema(tags=["Gallery Group"]),
)
class GalleryGroupViewSet(
    mixins.CreateModelMixin,
    mixins.ListModelMixin,
    mixins.RetrieveModelMixin,
    mixins.UpdateModelMixin,
    mixins.DestroyModelMixin,
    viewsets.GenericViewSet,
):
    permission_classes = [IsAuthenticatedAndActive, IsSchoolManagement]
    lookup_field = "pk"
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ["name"]
    ordering_fields = ["name", "created_at", "updated_at"]
    ordering = ["-created_at"]

    def get_queryset(self):
        school = get_school_for_user(self.request.user)
        return (
            GalleryGroup.objects
            .select_related("school", "created_by", "updated_by")
            .filter(school=school)
            .order_by("-created_at")
        )

    def get_serializer_class(self):
        if self.action == "create":
            return GalleryGroupCreateSerializer
        if self.action in ("update", "partial_update"):
            return GalleryGroupUpdateSerializer
        return GalleryGroupReadSerializer

    def create(self, request, *args, **kwargs):
        serializer = GalleryGroupCreateSerializer(data=request.data, context={"request": request})
        serializer.is_valid(raise_exception=True)
        obj = serializer.save()
        return Response({"message": "Gallery group created.", "data": GalleryGroupReadSerializer(obj).data}, status=status.HTTP_201_CREATED)

    def update(self, request, *args, **kwargs):
        obj = self.get_object()
        serializer = GalleryGroupUpdateSerializer(instance=obj, data=request.data, partial=False, context={"request": request})
        serializer.is_valid(raise_exception=True)
        obj = serializer.save()
        return Response({"message": "Gallery group updated.", "data": GalleryGroupReadSerializer(obj).data})

    def partial_update(self, request, *args, **kwargs):
        obj = self.get_object()
        serializer = GalleryGroupUpdateSerializer(instance=obj, data=request.data, partial=True, context={"request": request})
        serializer.is_valid(raise_exception=True)
        obj = serializer.save()
        return Response({"message": "Gallery group updated.", "data": GalleryGroupReadSerializer(obj).data})

    def destroy(self, request, *args, **kwargs):
        obj = self.get_object()
        obj.delete()
        return Response({"message": "Gallery group deleted successfully."}, status=status.HTTP_200_OK)


@extend_schema_view(
    list=extend_schema(tags=["Gallery Image"]),
    create=extend_schema(tags=["Gallery Image"], request=GalleryImageCreateSerializer),
    retrieve=extend_schema(tags=["Gallery Image"]),
    update=extend_schema(tags=["Gallery Image"], request=GalleryImageUpdateSerializer),
    partial_update=extend_schema(tags=["Gallery Image"], request=GalleryImageUpdateSerializer),
    destroy=extend_schema(tags=["Gallery Image"]),
)
class GalleryImageViewSet(
    mixins.CreateModelMixin,
    mixins.ListModelMixin,
    mixins.RetrieveModelMixin,
    mixins.UpdateModelMixin,
    mixins.DestroyModelMixin,
    viewsets.GenericViewSet,
):
    permission_classes = [IsAuthenticatedAndActive, IsSchoolManagement]
    lookup_field = "pk"
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ["caption", "gallery_group__name"]
    ordering_fields = ["caption", "created_at", "updated_at"]
    ordering = ["-created_at"]

    def get_queryset(self):
        school = get_school_for_user(self.request.user)
        return (
            GalleryImage.objects
            .select_related("image", "gallery_group", "created_by", "updated_by")
            .filter(gallery_group__school=school)
            .order_by("-created_at")
        )

    def get_serializer_class(self):
        if self.action == "create":
            return GalleryImageCreateSerializer
        if self.action in ("update", "partial_update"):
            return GalleryImageUpdateSerializer
        return GalleryImageReadSerializer

    def create(self, request, *args, **kwargs):
        serializer = GalleryImageCreateSerializer(data=request.data, context={"request": request})
        serializer.is_valid(raise_exception=True)
        obj = serializer.save()
        return Response({"message": "Gallery image created.", "data": GalleryImageReadSerializer(obj).data}, status=status.HTTP_201_CREATED)

    def update(self, request, *args, **kwargs):
        obj = self.get_object()
        serializer = GalleryImageUpdateSerializer(instance=obj, data=request.data, partial=False, context={"request": request})
        serializer.is_valid(raise_exception=True)
        obj = serializer.save()
        return Response({"message": "Gallery image updated.", "data": GalleryImageReadSerializer(obj).data})

    def partial_update(self, request, *args, **kwargs):
        obj = self.get_object()
        serializer = GalleryImageUpdateSerializer(instance=obj, data=request.data, partial=True, context={"request": request})
        serializer.is_valid(raise_exception=True)
        obj = serializer.save()
        return Response({"message": "Gallery image updated.", "data": GalleryImageReadSerializer(obj).data})

    def destroy(self, request, *args, **kwargs):
        obj = self.get_object()
        obj.delete()
        return Response({"message": "Gallery image deleted successfully."}, status=status.HTTP_200_OK)