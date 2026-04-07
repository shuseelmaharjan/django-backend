from __future__ import annotations

from typing import Any, Dict, List
from uuid import UUID

from django.db import IntegrityError, transaction
from django.core.exceptions import ValidationError as DjangoValidationError
from django.db.models import Max
from rest_framework import serializers

from utils.get_school_id_by_token import get_school_for_user
from website.models import Navigation, Courses, HomepageBanner, Icons, PrincipalMessage, Testimonial, Ads, Careers, AboutUs, Events, Blogs, FooterGroup, FooterLink, GalleryGroup, GalleryImage
from filehandler.serializers import UploadedFileSerializer


def _raise_django_validation(e: DjangoValidationError):
    if hasattr(e, "message_dict"):
        raise serializers.ValidationError(e.message_dict)
    raise serializers.ValidationError({"detail": e.messages})


class NavigationCreateSerializer(serializers.Serializer):
    name = serializers.CharField(max_length=100)
    slug = serializers.SlugField(max_length=100)

    def validate(self, attrs: Dict[str, Any]) -> Dict[str, Any]:
        request = self.context["request"]
        school = get_school_for_user(request.user)

        name = (attrs.get("name") or "").strip()
        slug = (attrs.get("slug") or "").strip().lower()

        if not name:
            raise serializers.ValidationError({"name": ["Name is required."]})
        if not slug:
            raise serializers.ValidationError({"slug": ["Slug is required."]})

        # If slug is globally unique in model, this still works.
        # If later you change uniqueness to school+slug, this is already scoped correctly.
        if Navigation.objects.filter(school=school, slug=slug).exists():
            raise serializers.ValidationError({"slug": ["This slug already exists in your school."]})

        attrs["name"] = name
        attrs["slug"] = slug
        attrs["_school"] = school
        return attrs

    def create(self, validated_data: Dict[str, Any]) -> Navigation:
        request = self.context["request"]
        school = validated_data["_school"]

        last_order = (
            Navigation.objects.filter(school=school).aggregate(max_order=Max("sort_order"))["max_order"]
        )
        next_order = 0 if last_order is None else last_order + 1

        obj = Navigation(
            name=validated_data["name"],
            slug=validated_data["slug"],
            school=school,
            sort_order=next_order,
            created_by=request.user,
            updated_by=request.user,
        )

        try:
            obj.full_clean()
            obj.save()
            return obj
        except DjangoValidationError as e:
            _raise_django_validation(e)
        except IntegrityError:
            raise serializers.ValidationError({"slug": ["This slug already exists."]})


class NavigationUpdateSerializer(serializers.Serializer):
    name = serializers.CharField(max_length=100, required=False)
    slug = serializers.SlugField(max_length=100, required=False)

    def validate(self, attrs: Dict[str, Any]) -> Dict[str, Any]:
        request = self.context["request"]
        school = get_school_for_user(request.user)
        instance: Navigation = self.instance

        if "name" in attrs:
            attrs["name"] = (attrs["name"] or "").strip()
            if not attrs["name"]:
                raise serializers.ValidationError({"name": ["Name is required."]})

        if "slug" in attrs:
            attrs["slug"] = (attrs["slug"] or "").strip().lower()
            if not attrs["slug"]:
                raise serializers.ValidationError({"slug": ["Slug is required."]})

            exists = Navigation.objects.filter(
                school=school,
                slug=attrs["slug"],
            ).exclude(id=instance.id).exists()

            if exists:
                raise serializers.ValidationError({"slug": ["This slug already exists in your school."]})

        return attrs

    def update(self, instance: Navigation, validated_data: Dict[str, Any]) -> Navigation:
        request = self.context["request"]

        if "name" in validated_data:
            instance.name = validated_data["name"]

        if "slug" in validated_data:
            instance.slug = validated_data["slug"]

        instance.updated_by = request.user

        try:
            instance.full_clean()
            instance.save()
            return instance
        except DjangoValidationError as e:
            _raise_django_validation(e)
        except IntegrityError:
            raise serializers.ValidationError({"slug": ["This slug already exists."]})


class NavigationReadSerializer(serializers.ModelSerializer):
    school_id = serializers.UUIDField(source="school.id", read_only=True, allow_null=True)
    created_by_id = serializers.UUIDField(source="created_by.id", read_only=True, allow_null=True)
    updated_by_id = serializers.UUIDField(source="updated_by.id", read_only=True, allow_null=True)

    class Meta:
        model = Navigation
        fields = [
            "id",
            "name",
            "slug",
            "school_id",
            "sort_order",
            "created_at",
            "created_by_id",
            "updated_at",
            "updated_by_id",
        ]


class NavigationReorderSerializer(serializers.Serializer):
    ordered_ids = serializers.ListField(
        child=serializers.UUIDField(),
        allow_empty=False,
        min_length=1,
    )

    def validate(self, attrs: Dict[str, Any]) -> Dict[str, Any]:
        request = self.context["request"]
        school = get_school_for_user(request.user)

        ids: List[UUID] = attrs["ordered_ids"]

        if len(ids) != len(set(ids)):
            raise serializers.ValidationError({"ordered_ids": ["Duplicate IDs are not allowed."]})

        existing = set(
            Navigation.objects.filter(school=school, id__in=ids).values_list("id", flat=True)
        )

        missing = [str(x) for x in ids if x not in existing]
        if missing:
            raise serializers.ValidationError(
                {"ordered_ids": [f"These IDs do not belong to your school: {missing}"]}
            )

        attrs["_school"] = school
        return attrs

    def save(self) -> Dict[str, Any]:
        school = self.validated_data["_school"]
        ids: List[UUID] = self.validated_data["ordered_ids"]

        with transaction.atomic():
            rows = list(
                Navigation.objects.select_for_update().filter(school=school, id__in=ids)
            )
            row_map = {row.id: row for row in rows}

            to_update = []
            for index, nav_id in enumerate(ids):
                row = row_map[nav_id]
                row.sort_order = index
                to_update.append(row)

            Navigation.objects.bulk_update(to_update, ["sort_order"])

        return {"updated": len(ids)}

# courses serializers

class CoursesCreateSerializer(serializers.Serializer):
    name = serializers.CharField(max_length=150)
    description = serializers.CharField(required=False, allow_blank=True, default="")
    navigation_id = serializers.UUIDField()
    slug = serializers.SlugField(max_length=150)
    image_id = serializers.UUIDField(required=False, allow_null=True)
    banner_id = serializers.UUIDField(required=False, allow_null=True)
    tags = serializers.CharField(required=False, allow_blank=True, default="")
    is_popular = serializers.BooleanField(required=False, default=False)

    def validate(self, attrs: Dict[str, Any]) -> Dict[str, Any]:
        request = self.context["request"]
        school = get_school_for_user(request.user)

        name = (attrs.get("name") or "").strip()
        description = (attrs.get("description") or "").strip()
        slug = (attrs.get("slug") or "").strip().lower()
        tags = (attrs.get("tags") or "").strip()

        if not name:
            raise serializers.ValidationError({"name": ["Name is required."]})
        if not slug:
            raise serializers.ValidationError({"slug": ["Slug is required."]})

        navigation_id = attrs.get("navigation_id")

        try:
            navigation = Navigation.objects.get(id=navigation_id, school=school)
        except Navigation.DoesNotExist:
            raise serializers.ValidationError(
                {"navigation_id": ["Selected navigation does not belong to your school."]}
            )

        if Courses.objects.filter(slug=slug).exists():
            raise serializers.ValidationError({"slug": ["This slug already exists."]})

        attrs["name"] = name
        attrs["description"] = description
        attrs["slug"] = slug
        attrs["tags"] = tags
        attrs["_school"] = school
        attrs["_navigation"] = navigation
        return attrs

    def create(self, validated_data: Dict[str, Any]) -> Courses:
        request = self.context["request"]
        school = validated_data["_school"]

        last_order = (
            Courses.objects.filter(school=school).aggregate(max_order=Max("sort_order"))["max_order"]
        )
        next_order = 0 if last_order is None else last_order + 1

        obj = Courses(
            name=validated_data["name"],
            description=validated_data.get("description", ""),
            navigation=validated_data["_navigation"],
            slug=validated_data["slug"],
            sort_order=next_order,
            image_id=validated_data.get("image_id"),
            banner_id=validated_data.get("banner_id"),
            school=school,
            tags=validated_data.get("tags", ""),
            is_popular=validated_data.get("is_popular", False),
            created_by=request.user,
            updated_by=request.user,
        )

        try:
            obj.full_clean()
            obj.save()
            return obj
        except DjangoValidationError as e:
            _raise_django_validation(e)
        except IntegrityError:
            raise serializers.ValidationError({"slug": ["This slug already exists."]})


class CoursesUpdateSerializer(serializers.Serializer):
    name = serializers.CharField(max_length=150, required=False)
    description = serializers.CharField(required=False, allow_blank=True)
    navigation_id = serializers.UUIDField(required=False)
    slug = serializers.SlugField(max_length=150, required=False)
    image_id = serializers.UUIDField(required=False, allow_null=True)
    banner_id = serializers.UUIDField(required=False, allow_null=True)
    tags = serializers.CharField(required=False, allow_blank=True)
    is_popular = serializers.BooleanField(required=False)

    def validate(self, attrs: Dict[str, Any]) -> Dict[str, Any]:
        request = self.context["request"]
        school = get_school_for_user(request.user)
        instance: Courses = self.instance

        if "name" in attrs:
            attrs["name"] = (attrs["name"] or "").strip()
            if not attrs["name"]:
                raise serializers.ValidationError({"name": ["Name is required."]})

        if "description" in attrs:
            attrs["description"] = (attrs["description"] or "").strip()

        if "tags" in attrs:
            attrs["tags"] = (attrs["tags"] or "").strip()

        if "slug" in attrs:
            attrs["slug"] = (attrs["slug"] or "").strip().lower()
            if not attrs["slug"]:
                raise serializers.ValidationError({"slug": ["Slug is required."]})

            exists = Courses.objects.filter(slug=attrs["slug"]).exclude(id=instance.id).exists()
            if exists:
                raise serializers.ValidationError({"slug": ["This slug already exists."]})

        if "navigation_id" in attrs:
            try:
                attrs["_navigation"] = Navigation.objects.get(
                    id=attrs["navigation_id"],
                    school=school,
                )
            except Navigation.DoesNotExist:
                raise serializers.ValidationError(
                    {"navigation_id": ["Selected navigation does not belong to your school."]}
                )

        return attrs

    def update(self, instance: Courses, validated_data: Dict[str, Any]) -> Courses:
        request = self.context["request"]

        if "name" in validated_data:
            instance.name = validated_data["name"]

        if "description" in validated_data:
            instance.description = validated_data["description"]

        if "_navigation" in validated_data:
            instance.navigation = validated_data["_navigation"]


        if "slug" in validated_data:
            instance.slug = validated_data["slug"]

        if "image_id" in validated_data:
            instance.image_id = validated_data["image_id"]

        if "banner_id" in validated_data:
            instance.banner_id = validated_data["banner_id"]

        if "tags" in validated_data:
            instance.tags = validated_data["tags"]

        if "is_popular" in validated_data:
            instance.is_popular = validated_data["is_popular"]

        instance.updated_by = request.user

        try:
            instance.full_clean()
            instance.save()
            return instance
        except DjangoValidationError as e:
            _raise_django_validation(e)
        except IntegrityError:
            raise serializers.ValidationError({"slug": ["This slug already exists."]})


class CoursesReadSerializer(serializers.ModelSerializer):
    school_id = serializers.UUIDField(source="school.id", read_only=True, allow_null=True)
    navigation_id = serializers.UUIDField(source="navigation.id", read_only=True)
    navigation_name = serializers.CharField(source="navigation.name", read_only=True)
    image = UploadedFileSerializer(read_only=True)
    banner = UploadedFileSerializer(read_only=True)
    created_by_id = serializers.UUIDField(source="created_by.id", read_only=True, allow_null=True)
    updated_by_id = serializers.UUIDField(source="updated_by.id", read_only=True, allow_null=True)

    class Meta:
        model = Courses
        fields = [
            "id",
            "name",
            "description",
            "navigation_id",
            "navigation_name",
            "slug",
            "sort_order",
            "image",
            "banner",
            "school_id",
            "tags",
            "is_popular",
            "created_at",
            "created_by_id",
            "updated_at",
            "updated_by_id",
        ]


class CoursesReorderSerializer(serializers.Serializer):
    ordered_ids = serializers.ListField(
        child=serializers.UUIDField(),
        allow_empty=False,
        min_length=1,
    )

    def validate(self, attrs: Dict[str, Any]) -> Dict[str, Any]:
        request = self.context["request"]
        school = get_school_for_user(request.user)

        ids: List[UUID] = attrs["ordered_ids"]

        if len(ids) != len(set(ids)):
            raise serializers.ValidationError({"ordered_ids": ["Duplicate IDs are not allowed."]})

        existing = set(
            Courses.objects.filter(school=school, id__in=ids).values_list("id", flat=True)
        )

        missing = [str(x) for x in ids if x not in existing]
        if missing:
            raise serializers.ValidationError(
                {"ordered_ids": [f"These IDs do not belong to your school: {missing}"]}
            )

        attrs["_school"] = school
        return attrs

    def save(self) -> Dict[str, Any]:
        school = self.validated_data["_school"]
        ids: List[UUID] = self.validated_data["ordered_ids"]

        with transaction.atomic():
            rows = list(
                Courses.objects.select_for_update().filter(school=school, id__in=ids)
            )
            row_map = {row.id: row for row in rows}

            to_update = []
            for index, course_id in enumerate(ids):
                row = row_map[course_id]
                row.sort_order = index
                to_update.append(row)

            Courses.objects.bulk_update(to_update, ["sort_order"])

        return {"updated": len(ids)}

# ------------------------------------
# Homepage serializers (if needed, otherwise you can directly use CoursesReadSerializer in views)
# ------------------------------------
class HomepageBannerCreateSerializer(serializers.Serializer):
    title = serializers.CharField(max_length=150)
    subtitle = serializers.CharField(max_length=255, required=False, allow_blank=True, default="")
    description = serializers.CharField(required=False, allow_blank=True, default="")
    image_id = serializers.UUIDField(required=False, allow_null=True)
    have_link = serializers.BooleanField(required=False, default=False)
    link_url = serializers.URLField(required=False, allow_blank=True, default="")
    button_link = serializers.CharField(max_length=100, required=False, allow_blank=True, default="")

    def validate(self, attrs: Dict[str, Any]) -> Dict[str, Any]:
        school = get_school_for_user(self.context["request"].user)

        title = (attrs.get("title") or "").strip()
        subtitle = (attrs.get("subtitle") or "").strip()
        description = (attrs.get("description") or "").strip()
        link_url = (attrs.get("link_url") or "").strip()
        button_link = (attrs.get("button_link") or "").strip()
        have_link = attrs.get("have_link", False)

        if not title:
            raise serializers.ValidationError({"title": ["Title is required."]})

        if have_link and not link_url:
            raise serializers.ValidationError({"link_url": ["Link URL is required when have_link is true."]})

        if not have_link:
            link_url = ""
            button_link = ""

        attrs["title"] = title
        attrs["subtitle"] = subtitle
        attrs["description"] = description
        attrs["link_url"] = link_url
        attrs["button_link"] = button_link
        attrs["_school"] = school
        return attrs

    def create(self, validated_data: Dict[str, Any]) -> HomepageBanner:
        request = self.context["request"]
        school = validated_data["_school"]

        last_order = (
            HomepageBanner.objects.filter(school=school).aggregate(max_order=Max("sort_order"))["max_order"]
        )
        next_order = 0 if last_order is None else last_order + 1

        obj = HomepageBanner(
            title=validated_data["title"],
            subtitle=validated_data.get("subtitle", ""),
            description=validated_data.get("description", ""),
            image_id=validated_data.get("image_id"),
            sort_order=next_order,
            have_link=validated_data.get("have_link", False),
            link_url=validated_data.get("link_url", ""),
            button_link=validated_data.get("button_link", ""),
            school=school,
            created_by=request.user,
            updated_by=request.user,
        )

        try:
            obj.full_clean()
            obj.save()
            return obj
        except DjangoValidationError as e:
            _raise_django_validation(e)


class HomepageBannerUpdateSerializer(serializers.Serializer):
    title = serializers.CharField(max_length=150, required=False)
    subtitle = serializers.CharField(max_length=255, required=False, allow_blank=True)
    description = serializers.CharField(required=False, allow_blank=True)
    image_id = serializers.UUIDField(required=False, allow_null=True)
    have_link = serializers.BooleanField(required=False)
    link_url = serializers.URLField(required=False, allow_blank=True)
    button_link = serializers.CharField(max_length=100, required=False, allow_blank=True)

    def validate(self, attrs: Dict[str, Any]) -> Dict[str, Any]:
        instance: HomepageBanner = self.instance

        title = attrs.get("title", instance.title)
        subtitle = attrs.get("subtitle", instance.subtitle)
        description = attrs.get("description", instance.description)
        have_link = attrs.get("have_link", instance.have_link)
        link_url = attrs.get("link_url", instance.link_url)
        button_link = attrs.get("button_link", instance.button_link)

        title = (title or "").strip()
        subtitle = (subtitle or "").strip()
        description = (description or "").strip()
        link_url = (link_url or "").strip()
        button_link = (button_link or "").strip()

        if not title:
            raise serializers.ValidationError({"title": ["Title is required."]})

        if have_link and not link_url:
            raise serializers.ValidationError({"link_url": ["Link URL is required when have_link is true."]})

        if "title" in attrs:
            attrs["title"] = title
        if "subtitle" in attrs:
            attrs["subtitle"] = subtitle
        if "description" in attrs:
            attrs["description"] = description
        if "link_url" in attrs:
            attrs["link_url"] = link_url
        if "button_link" in attrs:
            attrs["button_link"] = button_link

        if "have_link" in attrs and not attrs["have_link"]:
            attrs["link_url"] = ""
            attrs["button_link"] = ""

        return attrs

    def update(self, instance: HomepageBanner, validated_data: Dict[str, Any]) -> HomepageBanner:
        request = self.context["request"]

        if "title" in validated_data:
            instance.title = validated_data["title"]

        if "subtitle" in validated_data:
            instance.subtitle = validated_data["subtitle"]

        if "description" in validated_data:
            instance.description = validated_data["description"]

        if "image_id" in validated_data:
            instance.image_id = validated_data["image_id"]

        if "have_link" in validated_data:
            instance.have_link = validated_data["have_link"]

        if "link_url" in validated_data:
            instance.link_url = validated_data["link_url"]

        if "button_link" in validated_data:
            instance.button_link = validated_data["button_link"]

        instance.updated_by = request.user

        try:
            instance.full_clean()
            instance.save()
            return instance
        except DjangoValidationError as e:
            _raise_django_validation(e)


class HomepageBannerReadSerializer(serializers.ModelSerializer):
    school_id = serializers.UUIDField(source="school.id", read_only=True, allow_null=True)
    image = UploadedFileSerializer(read_only=True)
    created_by_id = serializers.UUIDField(source="created_by.id", read_only=True, allow_null=True)
    updated_by_id = serializers.UUIDField(source="updated_by.id", read_only=True, allow_null=True)

    class Meta:
        model = HomepageBanner
        fields = [
            "id",
            "title",
            "subtitle",
            "description",
            "image",
            "sort_order",
            "have_link",
            "link_url",
            "button_link",
            "school_id",
            "created_at",
            "created_by_id",
            "updated_at",
            "updated_by_id",
        ]


class HomepageBannerReorderSerializer(serializers.Serializer):
    ordered_ids = serializers.ListField(
        child=serializers.UUIDField(),
        allow_empty=False,
        min_length=1,
    )

    def validate(self, attrs: Dict[str, Any]) -> Dict[str, Any]:
        request = self.context["request"]
        school = get_school_for_user(request.user)

        ids: List[UUID] = attrs["ordered_ids"]

        if len(ids) != len(set(ids)):
            raise serializers.ValidationError({"ordered_ids": ["Duplicate IDs are not allowed."]})

        existing = set(
            HomepageBanner.objects.filter(school=school, id__in=ids).values_list("id", flat=True)
        )

        missing = [str(x) for x in ids if x not in existing]
        if missing:
            raise serializers.ValidationError(
                {"ordered_ids": [f"These IDs do not belong to your school: {missing}"]}
            )

        attrs["_school"] = school
        return attrs

    def save(self) -> Dict[str, Any]:
        school = self.validated_data["_school"]
        ids: List[UUID] = self.validated_data["ordered_ids"]

        with transaction.atomic():
            rows = list(
                HomepageBanner.objects.select_for_update().filter(school=school, id__in=ids)
            )
            row_map = {row.id: row for row in rows}

            to_update = []
            for index, banner_id in enumerate(ids):
                row = row_map[banner_id]
                row.sort_order = index
                to_update.append(row)

            HomepageBanner.objects.bulk_update(to_update, ["sort_order"])

        return {"updated": len(ids)}

# ------------------------
# Icons serializers (if needed, otherwise you can directly use IconsReadSerializer in views)
# ------------------------
class IconsCreateSerializer(serializers.Serializer):
    name = serializers.CharField(max_length=100)
    image_id = serializers.UUIDField(required=False, allow_null=True)

    def validate(self, attrs: Dict[str, Any]) -> Dict[str, Any]:
        school = get_school_for_user(self.context["request"].user)

        name = (attrs.get("name") or "").strip()
        if not name:
            raise serializers.ValidationError({"name": ["Name is required."]})

        attrs["name"] = name
        attrs["_school"] = school
        return attrs

    def create(self, validated_data: Dict[str, Any]) -> Icons:
        request = self.context["request"]
        school = validated_data["_school"]

        last_order = Icons.objects.filter(school=school).aggregate(max_order=Max("sort_order"))["max_order"]
        next_order = 0 if last_order is None else last_order + 1

        obj = Icons(
            name=validated_data["name"],
            image_id=validated_data.get("image_id"),
            sort_order=next_order,
            school=school,
            created_by=request.user,
            updated_by=request.user,
        )

        try:
            obj.full_clean()
            obj.save()
            return obj
        except DjangoValidationError as e:
            _raise_django_validation(e)


class IconsUpdateSerializer(serializers.Serializer):
    name = serializers.CharField(max_length=100, required=False)
    image_id = serializers.UUIDField(required=False, allow_null=True)

    def validate(self, attrs: Dict[str, Any]) -> Dict[str, Any]:
        if "name" in attrs:
            attrs["name"] = (attrs["name"] or "").strip()
            if not attrs["name"]:
                raise serializers.ValidationError({"name": ["Name is required."]})
        return attrs

    def update(self, instance: Icons, validated_data: Dict[str, Any]) -> Icons:
        request = self.context["request"]

        if "name" in validated_data:
            instance.name = validated_data["name"]

        if "image_id" in validated_data:
            instance.image_id = validated_data["image_id"]

        instance.updated_by = request.user

        try:
            instance.full_clean()
            instance.save()
            return instance
        except DjangoValidationError as e:
            _raise_django_validation(e)


class IconsReadSerializer(serializers.ModelSerializer):
    school_id = serializers.UUIDField(source="school.id", read_only=True, allow_null=True)
    image = UploadedFileSerializer(read_only=True)
    created_by_id = serializers.UUIDField(source="created_by.id", read_only=True, allow_null=True)
    updated_by_id = serializers.UUIDField(source="updated_by.id", read_only=True, allow_null=True)

    class Meta:
        model = Icons
        fields = [
            "id",
            "name",
            "image",
            "sort_order",
            "school_id",
            "created_at",
            "created_by_id",
            "updated_at",
            "updated_by_id",
        ]


class IconsReorderSerializer(serializers.Serializer):
    ordered_ids = serializers.ListField(
        child=serializers.UUIDField(),
        allow_empty=False,
        min_length=1,
    )

    def validate(self, attrs: Dict[str, Any]) -> Dict[str, Any]:
        request = self.context["request"]
        school = get_school_for_user(request.user)
        ids: List[UUID] = attrs["ordered_ids"]

        if len(ids) != len(set(ids)):
            raise serializers.ValidationError({"ordered_ids": ["Duplicate IDs are not allowed."]})

        existing = set(Icons.objects.filter(school=school, id__in=ids).values_list("id", flat=True))
        missing = [str(x) for x in ids if x not in existing]

        if missing:
            raise serializers.ValidationError(
                {"ordered_ids": [f"These IDs do not belong to your school: {missing}"]}
            )

        attrs["_school"] = school
        return attrs

    def save(self) -> Dict[str, Any]:
        school = self.validated_data["_school"]
        ids: List[UUID] = self.validated_data["ordered_ids"]

        with transaction.atomic():
            rows = list(Icons.objects.select_for_update().filter(school=school, id__in=ids))
            row_map = {row.id: row for row in rows}

            to_update = []
            for index, icon_id in enumerate(ids):
                row = row_map[icon_id]
                row.sort_order = index
                to_update.append(row)

            Icons.objects.bulk_update(to_update, ["sort_order"])

        return {"updated": len(ids)}

# ------------------------
# PrincipalMessage and Testimonial serializers would follow a similar pattern to HomepageBanner and Icons, with fields specific to their models. You can create Create, Update, Read, and Reorder serializers for them as needed, following the same structure as shown above.
# ------------------------
class PrincipalMessageCreateSerializer(serializers.Serializer):
    title = serializers.CharField(max_length=150)
    message = serializers.CharField(required=False, allow_blank=True, default="")
    image_id = serializers.UUIDField(required=False, allow_null=True)

    def validate(self, attrs: Dict[str, Any]) -> Dict[str, Any]:
        school = get_school_for_user(self.context["request"].user)

        title = (attrs.get("title") or "").strip()
        message = (attrs.get("message") or "").strip()

        if not title:
            raise serializers.ValidationError({"title": ["Title is required."]})

        attrs["title"] = title
        attrs["message"] = message
        attrs["_school"] = school
        return attrs

    def create(self, validated_data: Dict[str, Any]) -> PrincipalMessage:
        request = self.context["request"]

        obj = PrincipalMessage(
            title=validated_data["title"],
            message=validated_data.get("message", ""),
            image_id=validated_data.get("image_id"),
            school=validated_data["_school"],
            created_by=request.user,
            updated_by=request.user,
        )

        try:
            obj.full_clean()
            obj.save()
            return obj
        except DjangoValidationError as e:
            _raise_django_validation(e)


class PrincipalMessageUpdateSerializer(serializers.Serializer):
    title = serializers.CharField(max_length=150, required=False)
    message = serializers.CharField(required=False, allow_blank=True)
    image_id = serializers.UUIDField(required=False, allow_null=True)

    def validate(self, attrs: Dict[str, Any]) -> Dict[str, Any]:
        if "title" in attrs:
            attrs["title"] = (attrs["title"] or "").strip()
            if not attrs["title"]:
                raise serializers.ValidationError({"title": ["Title is required."]})

        if "message" in attrs:
            attrs["message"] = (attrs["message"] or "").strip()

        return attrs

    def update(self, instance: PrincipalMessage, validated_data: Dict[str, Any]) -> PrincipalMessage:
        request = self.context["request"]

        if "title" in validated_data:
            instance.title = validated_data["title"]

        if "message" in validated_data:
            instance.message = validated_data["message"]

        if "image_id" in validated_data:
            instance.image_id = validated_data["image_id"]

        instance.updated_by = request.user

        try:
            instance.full_clean()
            instance.save()
            return instance
        except DjangoValidationError as e:
            _raise_django_validation(e)


class PrincipalMessageReadSerializer(serializers.ModelSerializer):
    school_id = serializers.UUIDField(source="school.id", read_only=True, allow_null=True)
    image = UploadedFileSerializer(read_only=True)
    created_by_id = serializers.UUIDField(source="created_by.id", read_only=True, allow_null=True)
    updated_by_id = serializers.UUIDField(source="updated_by.id", read_only=True, allow_null=True)

    class Meta:
        model = PrincipalMessage
        fields = [
            "id",
            "title",
            "message",
            "image",
            "school_id",
            "created_at",
            "created_by_id",
            "updated_at",
            "updated_by_id",
        ]

class IconsCreateSerializer(serializers.Serializer):
    name = serializers.CharField(max_length=100)
    image_id = serializers.UUIDField(required=False, allow_null=True)

    def validate(self, attrs: Dict[str, Any]) -> Dict[str, Any]:
        school = get_school_for_user(self.context["request"].user)

        name = (attrs.get("name") or "").strip()
        if not name:
            raise serializers.ValidationError({"name": ["Name is required."]})

        attrs["name"] = name
        attrs["_school"] = school
        return attrs

    def create(self, validated_data: Dict[str, Any]) -> Icons:
        request = self.context["request"]
        school = validated_data["_school"]

        last_order = Icons.objects.filter(school=school).aggregate(max_order=Max("sort_order"))["max_order"]
        next_order = 0 if last_order is None else last_order + 1

        obj = Icons(
            name=validated_data["name"],
            image_id=validated_data.get("image_id"),
            sort_order=next_order,
            school=school,
            created_by=request.user,
            updated_by=request.user,
        )

        try:
            obj.full_clean()
            obj.save()
            return obj
        except DjangoValidationError as e:
            _raise_django_validation(e)


class IconsUpdateSerializer(serializers.Serializer):
    name = serializers.CharField(max_length=100, required=False)
    image_id = serializers.UUIDField(required=False, allow_null=True)

    def validate(self, attrs: Dict[str, Any]) -> Dict[str, Any]:
        if "name" in attrs:
            attrs["name"] = (attrs["name"] or "").strip()
            if not attrs["name"]:
                raise serializers.ValidationError({"name": ["Name is required."]})
        return attrs

    def update(self, instance: Icons, validated_data: Dict[str, Any]) -> Icons:
        request = self.context["request"]

        if "name" in validated_data:
            instance.name = validated_data["name"]

        if "image_id" in validated_data:
            instance.image_id = validated_data["image_id"]

        instance.updated_by = request.user

        try:
            instance.full_clean()
            instance.save()
            return instance
        except DjangoValidationError as e:
            _raise_django_validation(e)


class IconsReadSerializer(serializers.ModelSerializer):
    school_id = serializers.UUIDField(source="school.id", read_only=True, allow_null=True)
    image = UploadedFileSerializer(read_only=True)
    created_by_id = serializers.UUIDField(source="created_by.id", read_only=True, allow_null=True)
    updated_by_id = serializers.UUIDField(source="updated_by.id", read_only=True, allow_null=True)

    class Meta:
        model = Icons
        fields = [
            "id",
            "name",
            "image",
            "sort_order",
            "school_id",
            "created_at",
            "created_by_id",
            "updated_at",
            "updated_by_id",
        ]


class IconsReorderSerializer(serializers.Serializer):
    ordered_ids = serializers.ListField(
        child=serializers.UUIDField(),
        allow_empty=False,
        min_length=1,
    )

    def validate(self, attrs: Dict[str, Any]) -> Dict[str, Any]:
        request = self.context["request"]
        school = get_school_for_user(request.user)
        ids: List[UUID] = attrs["ordered_ids"]

        if len(ids) != len(set(ids)):
            raise serializers.ValidationError({"ordered_ids": ["Duplicate IDs are not allowed."]})

        existing = set(Icons.objects.filter(school=school, id__in=ids).values_list("id", flat=True))
        missing = [str(x) for x in ids if x not in existing]

        if missing:
            raise serializers.ValidationError(
                {"ordered_ids": [f"These IDs do not belong to your school: {missing}"]}
            )

        attrs["_school"] = school
        return attrs

    def save(self) -> Dict[str, Any]:
        school = self.validated_data["_school"]
        ids: List[UUID] = self.validated_data["ordered_ids"]

        with transaction.atomic():
            rows = list(Icons.objects.select_for_update().filter(school=school, id__in=ids))
            row_map = {row.id: row for row in rows}

            to_update = []
            for index, icon_id in enumerate(ids):
                row = row_map[icon_id]
                row.sort_order = index
                to_update.append(row)

            Icons.objects.bulk_update(to_update, ["sort_order"])

        return {"updated": len(ids)}

# -------------------------
# Testimonial Serializers
# -------------------------
class TestimonialCreateSerializer(serializers.Serializer):
    name = serializers.CharField(max_length=100)
    role = serializers.CharField(max_length=100, required=False, allow_blank=True, default="")
    message = serializers.CharField(required=False, allow_blank=True, default="")
    image_id = serializers.UUIDField(required=False, allow_null=True)

    def validate(self, attrs: Dict[str, Any]) -> Dict[str, Any]:
        school = get_school_for_user(self.context["request"].user)

        name = (attrs.get("name") or "").strip()
        role = (attrs.get("role") or "").strip()
        message = (attrs.get("message") or "").strip()

        if not name:
            raise serializers.ValidationError({"name": ["Name is required."]})

        attrs["name"] = name
        attrs["role"] = role
        attrs["message"] = message
        attrs["_school"] = school
        return attrs

    def create(self, validated_data: Dict[str, Any]) -> Testimonial:
        request = self.context["request"]

        obj = Testimonial(
            name=validated_data["name"],
            role=validated_data.get("role", ""),
            message=validated_data.get("message", ""),
            image_id=validated_data.get("image_id"),
            school=validated_data["_school"],
            created_by=request.user,
            updated_by=request.user,
        )

        try:
            obj.full_clean()
            obj.save()
            return obj
        except DjangoValidationError as e:
            _raise_django_validation(e)


class TestimonialUpdateSerializer(serializers.Serializer):
    name = serializers.CharField(max_length=100, required=False)
    role = serializers.CharField(max_length=100, required=False, allow_blank=True)
    message = serializers.CharField(required=False, allow_blank=True)
    image_id = serializers.UUIDField(required=False, allow_null=True)

    def validate(self, attrs: Dict[str, Any]) -> Dict[str, Any]:
        if "name" in attrs:
            attrs["name"] = (attrs["name"] or "").strip()
            if not attrs["name"]:
                raise serializers.ValidationError({"name": ["Name is required."]})

        if "role" in attrs:
            attrs["role"] = (attrs["role"] or "").strip()

        if "message" in attrs:
            attrs["message"] = (attrs["message"] or "").strip()

        return attrs

    def update(self, instance: Testimonial, validated_data: Dict[str, Any]) -> Testimonial:
        request = self.context["request"]

        if "name" in validated_data:
            instance.name = validated_data["name"]

        if "role" in validated_data:
            instance.role = validated_data["role"]

        if "message" in validated_data:
            instance.message = validated_data["message"]

        if "image_id" in validated_data:
            instance.image_id = validated_data["image_id"]

        instance.updated_by = request.user

        try:
            instance.full_clean()
            instance.save()
            return instance
        except DjangoValidationError as e:
            _raise_django_validation(e)


class TestimonialReadSerializer(serializers.ModelSerializer):
    school_id = serializers.UUIDField(source="school.id", read_only=True, allow_null=True)
    image = UploadedFileSerializer(read_only=True)
    created_by_id = serializers.UUIDField(source="created_by.id", read_only=True, allow_null=True)
    updated_by_id = serializers.UUIDField(source="updated_by.id", read_only=True, allow_null=True)

    class Meta:
        model = Testimonial
        fields = [
            "id",
            "name",
            "role",
            "message",
            "image",
            "school_id",
            "created_at",
            "created_by_id",
            "updated_at",
            "updated_by_id",
        ]

# --------------------------
# Ads Serializers (if needed, otherwise you can directly use AdsReadSerializer in views)
# --------------------------
class AdsCreateSerializer(serializers.Serializer):
    title = serializers.CharField(max_length=150)
    description = serializers.CharField(required=False, allow_blank=True, default="")
    image_id = serializers.UUIDField(required=False, allow_null=True)
    link_url = serializers.URLField(required=False, allow_blank=True, default="")

    def validate(self, attrs: Dict[str, Any]) -> Dict[str, Any]:
        school = get_school_for_user(self.context["request"].user)

        title = (attrs.get("title") or "").strip()
        description = (attrs.get("description") or "").strip()
        link_url = (attrs.get("link_url") or "").strip()

        if not title:
            raise serializers.ValidationError({"title": ["Title is required."]})

        attrs["title"] = title
        attrs["description"] = description
        attrs["link_url"] = link_url
        attrs["_school"] = school
        return attrs

    def create(self, validated_data: Dict[str, Any]) -> Ads:
        request = self.context["request"]

        obj = Ads(
            title=validated_data["title"],
            description=validated_data.get("description", ""),
            image_id=validated_data.get("image_id"),
            link_url=validated_data.get("link_url", ""),
            school=validated_data["_school"],
            created_by=request.user,
            updated_by=request.user,
        )

        try:
            obj.full_clean()
            obj.save()
            return obj
        except DjangoValidationError as e:
            _raise_django_validation(e)


class AdsUpdateSerializer(serializers.Serializer):
    title = serializers.CharField(max_length=150, required=False)
    description = serializers.CharField(required=False, allow_blank=True)
    image_id = serializers.UUIDField(required=False, allow_null=True)
    link_url = serializers.URLField(required=False, allow_blank=True)

    def validate(self, attrs: Dict[str, Any]) -> Dict[str, Any]:
        if "title" in attrs:
            attrs["title"] = (attrs["title"] or "").strip()
            if not attrs["title"]:
                raise serializers.ValidationError({"title": ["Title is required."]})

        if "description" in attrs:
            attrs["description"] = (attrs["description"] or "").strip()

        if "link_url" in attrs:
            attrs["link_url"] = (attrs["link_url"] or "").strip()

        return attrs

    def update(self, instance: Ads, validated_data: Dict[str, Any]) -> Ads:
        request = self.context["request"]

        if "title" in validated_data:
            instance.title = validated_data["title"]

        if "description" in validated_data:
            instance.description = validated_data["description"]

        if "image_id" in validated_data:
            instance.image_id = validated_data["image_id"]

        if "link_url" in validated_data:
            instance.link_url = validated_data["link_url"]

        instance.updated_by = request.user

        try:
            instance.full_clean()
            instance.save()
            return instance
        except DjangoValidationError as e:
            _raise_django_validation(e)


class AdsReadSerializer(serializers.ModelSerializer):
    school_id = serializers.UUIDField(source="school.id", read_only=True, allow_null=True)
    image = UploadedFileSerializer(read_only=True)
    created_by_id = serializers.UUIDField(source="created_by.id", read_only=True, allow_null=True)
    updated_by_id = serializers.UUIDField(source="updated_by.id", read_only=True, allow_null=True)

    class Meta:
        model = Ads
        fields = [
            "id",
            "title",
            "description",
            "image",
            "link_url",
            "school_id",
            "created_at",
            "created_by_id",
            "updated_at",
            "updated_by_id",
        ]

class CareersCreateSerializer(serializers.Serializer):
    title = serializers.CharField(max_length=150)
    position = serializers.CharField(max_length=150, required=False, allow_blank=True, default="")
    job_description = serializers.CharField(required=False, allow_blank=True, default="")
    requirements = serializers.CharField(required=False, allow_blank=True, default="")
    expires_at = serializers.DateTimeField(required=False, allow_null=True)

    def validate(self, attrs: Dict[str, Any]) -> Dict[str, Any]:
        school = get_school_for_user(self.context["request"].user)

        title = (attrs.get("title") or "").strip()
        position = (attrs.get("position") or "").strip()
        job_description = (attrs.get("job_description") or "").strip()
        requirements = (attrs.get("requirements") or "").strip()

        if not title:
            raise serializers.ValidationError({"title": ["Title is required."]})

        attrs["title"] = title
        attrs["position"] = position
        attrs["job_description"] = job_description
        attrs["requirements"] = requirements
        attrs["_school"] = school
        return attrs

    def create(self, validated_data: Dict[str, Any]) -> Careers:
        request = self.context["request"]

        obj = Careers(
            title=validated_data["title"],
            position=validated_data.get("position", ""),
            job_description=validated_data.get("job_description", ""),
            requirements=validated_data.get("requirements", ""),
            expires_at=validated_data.get("expires_at"),
            school=validated_data["_school"],
            created_by=request.user,
            updated_by=request.user,
        )

        try:
            obj.full_clean()
            obj.save()
            return obj
        except DjangoValidationError as e:
            _raise_django_validation(e)


class CareersUpdateSerializer(serializers.Serializer):
    title = serializers.CharField(max_length=150, required=False)
    position = serializers.CharField(max_length=150, required=False, allow_blank=True)
    job_description = serializers.CharField(required=False, allow_blank=True)
    requirements = serializers.CharField(required=False, allow_blank=True)
    expires_at = serializers.DateTimeField(required=False, allow_null=True)

    def validate(self, attrs: Dict[str, Any]) -> Dict[str, Any]:
        if "title" in attrs:
            attrs["title"] = (attrs["title"] or "").strip()
            if not attrs["title"]:
                raise serializers.ValidationError({"title": ["Title is required."]})

        if "position" in attrs:
            attrs["position"] = (attrs["position"] or "").strip()

        if "job_description" in attrs:
            attrs["job_description"] = (attrs["job_description"] or "").strip()

        if "requirements" in attrs:
            attrs["requirements"] = (attrs["requirements"] or "").strip()

        return attrs

    def update(self, instance: Careers, validated_data: Dict[str, Any]) -> Careers:
        request = self.context["request"]

        if "title" in validated_data:
            instance.title = validated_data["title"]
        if "position" in validated_data:
            instance.position = validated_data["position"]
        if "job_description" in validated_data:
            instance.job_description = validated_data["job_description"]
        if "requirements" in validated_data:
            instance.requirements = validated_data["requirements"]
        if "expires_at" in validated_data:
            instance.expires_at = validated_data["expires_at"]

        instance.updated_by = request.user

        try:
            instance.full_clean()
            instance.save()
            return instance
        except DjangoValidationError as e:
            _raise_django_validation(e)


class CareersReadSerializer(serializers.ModelSerializer):
    school_id = serializers.UUIDField(source="school.id", read_only=True, allow_null=True)
    created_by_id = serializers.UUIDField(source="created_by.id", read_only=True, allow_null=True)
    updated_by_id = serializers.UUIDField(source="updated_by.id", read_only=True, allow_null=True)

    class Meta:
        model = Careers
        fields = [
            "id",
            "title",
            "position",
            "job_description",
            "requirements",
            "expires_at",
            "school_id",
            "created_at",
            "created_by_id",
            "updated_at",
            "updated_by_id",
        ]

class AboutUsCreateSerializer(serializers.Serializer):
    title = serializers.CharField(max_length=150)
    description = serializers.CharField(required=False, allow_blank=True, default="")
    image_id = serializers.UUIDField(required=False, allow_null=True)

    def validate(self, attrs: Dict[str, Any]) -> Dict[str, Any]:
        school = get_school_for_user(self.context["request"].user)

        title = (attrs.get("title") or "").strip()
        description = (attrs.get("description") or "").strip()

        if not title:
            raise serializers.ValidationError({"title": ["Title is required."]})

        attrs["title"] = title
        attrs["description"] = description
        attrs["_school"] = school
        return attrs

    def create(self, validated_data: Dict[str, Any]) -> AboutUs:
        request = self.context["request"]

        obj = AboutUs(
            title=validated_data["title"],
            description=validated_data.get("description", ""),
            image_id=validated_data.get("image_id"),
            school=validated_data["_school"],
            created_by=request.user,
            updated_by=request.user,
        )

        try:
            obj.full_clean()
            obj.save()
            return obj
        except DjangoValidationError as e:
            _raise_django_validation(e)


class AboutUsUpdateSerializer(serializers.Serializer):
    title = serializers.CharField(max_length=150, required=False)
    description = serializers.CharField(required=False, allow_blank=True)
    image_id = serializers.UUIDField(required=False, allow_null=True)

    def validate(self, attrs: Dict[str, Any]) -> Dict[str, Any]:
        if "title" in attrs:
            attrs["title"] = (attrs["title"] or "").strip()
            if not attrs["title"]:
                raise serializers.ValidationError({"title": ["Title is required."]})

        if "description" in attrs:
            attrs["description"] = (attrs["description"] or "").strip()

        return attrs

    def update(self, instance: AboutUs, validated_data: Dict[str, Any]) -> AboutUs:
        request = self.context["request"]

        if "title" in validated_data:
            instance.title = validated_data["title"]
        if "description" in validated_data:
            instance.description = validated_data["description"]
        if "image_id" in validated_data:
            instance.image_id = validated_data["image_id"]

        instance.updated_by = request.user

        try:
            instance.full_clean()
            instance.save()
            return instance
        except DjangoValidationError as e:
            _raise_django_validation(e)


class AboutUsReadSerializer(serializers.ModelSerializer):
    school_id = serializers.UUIDField(source="school.id", read_only=True, allow_null=True)
    image = UploadedFileSerializer(read_only=True)
    created_by_id = serializers.UUIDField(source="created_by.id", read_only=True, allow_null=True)
    updated_by_id = serializers.UUIDField(source="updated_by.id", read_only=True, allow_null=True)

    class Meta:
        model = AboutUs
        fields = [
            "id",
            "title",
            "description",
            "image",
            "school_id",
            "created_at",
            "created_by_id",
            "updated_at",
            "updated_by_id",
        ]

class EventsCreateSerializer(serializers.Serializer):
    title = serializers.CharField(max_length=150)
    description = serializers.CharField(required=False, allow_blank=True, default="")
    event_date = serializers.DateTimeField(required=False, allow_null=True)

    def validate(self, attrs: Dict[str, Any]) -> Dict[str, Any]:
        title = (attrs.get("title") or "").strip()
        description = (attrs.get("description") or "").strip()

        if not title:
            raise serializers.ValidationError({"title": ["Title is required."]})

        attrs["title"] = title
        attrs["description"] = description
        return attrs

    def create(self, validated_data: Dict[str, Any]) -> Events:
        request = self.context["request"]

        obj = Events(
            title=validated_data["title"],
            description=validated_data.get("description", ""),
            event_date=validated_data.get("event_date"),
            created_by=request.user,
            updated_by=request.user,
        )

        try:
            obj.full_clean()
            obj.save()
            return obj
        except DjangoValidationError as e:
            _raise_django_validation(e)


class EventsUpdateSerializer(serializers.Serializer):
    title = serializers.CharField(max_length=150, required=False)
    description = serializers.CharField(required=False, allow_blank=True)
    event_date = serializers.DateTimeField(required=False, allow_null=True)

    def validate(self, attrs: Dict[str, Any]) -> Dict[str, Any]:
        if "title" in attrs:
            attrs["title"] = (attrs["title"] or "").strip()
            if not attrs["title"]:
                raise serializers.ValidationError({"title": ["Title is required."]})

        if "description" in attrs:
            attrs["description"] = (attrs["description"] or "").strip()

        return attrs

    def update(self, instance: Events, validated_data: Dict[str, Any]) -> Events:
        request = self.context["request"]

        if "title" in validated_data:
            instance.title = validated_data["title"]
        if "description" in validated_data:
            instance.description = validated_data["description"]
        if "event_date" in validated_data:
            instance.event_date = validated_data["event_date"]

        instance.updated_by = request.user

        try:
            instance.full_clean()
            instance.save()
            return instance
        except DjangoValidationError as e:
            _raise_django_validation(e)


class EventsReadSerializer(serializers.ModelSerializer):
    created_by_id = serializers.UUIDField(source="created_by.id", read_only=True, allow_null=True)
    updated_by_id = serializers.UUIDField(source="updated_by.id", read_only=True, allow_null=True)

    class Meta:
        model = Events
        fields = [
            "id",
            "title",
            "description",
            "event_date",
            "created_at",
            "created_by_id",
            "updated_at",
            "updated_by_id",
        ]

class BlogsCreateSerializer(serializers.Serializer):
    title = serializers.CharField(max_length=150)
    content = serializers.CharField(required=False, allow_blank=True, default="")
    author = serializers.CharField(max_length=100, required=False, allow_blank=True, default="")
    published_at = serializers.DateTimeField(required=False, allow_null=True)

    def validate(self, attrs: Dict[str, Any]) -> Dict[str, Any]:
        title = (attrs.get("title") or "").strip()
        content = (attrs.get("content") or "").strip()
        author = (attrs.get("author") or "").strip()

        if not title:
            raise serializers.ValidationError({"title": ["Title is required."]})

        attrs["title"] = title
        attrs["content"] = content
        attrs["author"] = author
        return attrs

    def create(self, validated_data: Dict[str, Any]) -> Blogs:
        request = self.context["request"]

        obj = Blogs(
            title=validated_data["title"],
            content=validated_data.get("content", ""),
            author=validated_data.get("author", ""),
            published_at=validated_data.get("published_at"),
            created_by=request.user,
            updated_by=request.user,
        )

        try:
            obj.full_clean()
            obj.save()
            return obj
        except DjangoValidationError as e:
            _raise_django_validation(e)


class BlogsUpdateSerializer(serializers.Serializer):
    title = serializers.CharField(max_length=150, required=False)
    content = serializers.CharField(required=False, allow_blank=True)
    author = serializers.CharField(max_length=100, required=False, allow_blank=True)
    published_at = serializers.DateTimeField(required=False, allow_null=True)

    def validate(self, attrs: Dict[str, Any]) -> Dict[str, Any]:
        if "title" in attrs:
            attrs["title"] = (attrs["title"] or "").strip()
            if not attrs["title"]:
                raise serializers.ValidationError({"title": ["Title is required."]})

        if "content" in attrs:
            attrs["content"] = (attrs["content"] or "").strip()

        if "author" in attrs:
            attrs["author"] = (attrs["author"] or "").strip()

        return attrs

    def update(self, instance: Blogs, validated_data: Dict[str, Any]) -> Blogs:
        request = self.context["request"]

        if "title" in validated_data:
            instance.title = validated_data["title"]
        if "content" in validated_data:
            instance.content = validated_data["content"]
        if "author" in validated_data:
            instance.author = validated_data["author"]
        if "published_at" in validated_data:
            instance.published_at = validated_data["published_at"]

        instance.updated_by = request.user

        try:
            instance.full_clean()
            instance.save()
            return instance
        except DjangoValidationError as e:
            _raise_django_validation(e)


class BlogsReadSerializer(serializers.ModelSerializer):
    created_by_id = serializers.UUIDField(source="created_by.id", read_only=True, allow_null=True)
    updated_by_id = serializers.UUIDField(source="updated_by.id", read_only=True, allow_null=True)

    class Meta:
        model = Blogs
        fields = [
            "id",
            "title",
            "content",
            "author",
            "published_at",
            "created_at",
            "created_by_id",
            "updated_at",
            "updated_by_id",
        ]

class FooterGroupCreateSerializer(serializers.Serializer):
    name = serializers.CharField(max_length=100)

    def validate(self, attrs: Dict[str, Any]) -> Dict[str, Any]:
        school = get_school_for_user(self.context["request"].user)
        name = (attrs.get("name") or "").strip()

        if not name:
            raise serializers.ValidationError({"name": ["Name is required."]})

        attrs["name"] = name
        attrs["_school"] = school
        return attrs

    def create(self, validated_data: Dict[str, Any]) -> FooterGroup:
        request = self.context["request"]

        obj = FooterGroup(
            name=validated_data["name"],
            school=validated_data["_school"],
            created_by=request.user,
            updated_by=request.user,
        )

        try:
            obj.full_clean()
            obj.save()
            return obj
        except DjangoValidationError as e:
            _raise_django_validation(e)


class FooterGroupUpdateSerializer(serializers.Serializer):
    name = serializers.CharField(max_length=100, required=False)

    def validate(self, attrs: Dict[str, Any]) -> Dict[str, Any]:
        if "name" in attrs:
            attrs["name"] = (attrs["name"] or "").strip()
            if not attrs["name"]:
                raise serializers.ValidationError({"name": ["Name is required."]})
        return attrs

    def update(self, instance: FooterGroup, validated_data: Dict[str, Any]) -> FooterGroup:
        request = self.context["request"]

        if "name" in validated_data:
            instance.name = validated_data["name"]

        instance.updated_by = request.user

        try:
            instance.full_clean()
            instance.save()
            return instance
        except DjangoValidationError as e:
            _raise_django_validation(e)


class FooterGroupReadSerializer(serializers.ModelSerializer):
    school_id = serializers.UUIDField(source="school.id", read_only=True, allow_null=True)
    created_by_id = serializers.UUIDField(source="created_by.id", read_only=True, allow_null=True)
    updated_by_id = serializers.UUIDField(source="updated_by.id", read_only=True, allow_null=True)

    class Meta:
        model = FooterGroup
        fields = [
            "id",
            "name",
            "school_id",
            "created_at",
            "created_by_id",
            "updated_at",
            "updated_by_id",
        ]

class FooterLinkCreateSerializer(serializers.Serializer):
    name = serializers.CharField(max_length=100)
    url = serializers.URLField(required=False, allow_blank=True, default="")
    footer_group_id = serializers.UUIDField()

    def validate(self, attrs: Dict[str, Any]) -> Dict[str, Any]:
        request = self.context["request"]
        school = get_school_for_user(request.user)

        name = (attrs.get("name") or "").strip()
        url = (attrs.get("url") or "").strip()
        footer_group_id = attrs.get("footer_group_id")

        if not name:
            raise serializers.ValidationError({"name": ["Name is required."]})

        try:
            footer_group = FooterGroup.objects.get(id=footer_group_id, school=school)
        except FooterGroup.DoesNotExist:
            raise serializers.ValidationError(
                {"footer_group_id": ["Selected footer group does not belong to your school."]}
            )

        attrs["name"] = name
        attrs["url"] = url
        attrs["_footer_group"] = footer_group
        return attrs

    def create(self, validated_data: Dict[str, Any]) -> FooterLink:
        request = self.context["request"]

        obj = FooterLink(
            name=validated_data["name"],
            url=validated_data.get("url", ""),
            footer_group=validated_data["_footer_group"],
            created_by=request.user,
            updated_by=request.user,
        )

        try:
            obj.full_clean()
            obj.save()
            return obj
        except DjangoValidationError as e:
            _raise_django_validation(e)


class FooterLinkUpdateSerializer(serializers.Serializer):
    name = serializers.CharField(max_length=100, required=False)
    url = serializers.URLField(required=False, allow_blank=True)
    footer_group_id = serializers.UUIDField(required=False)

    def validate(self, attrs: Dict[str, Any]) -> Dict[str, Any]:
        request = self.context["request"]
        school = get_school_for_user(request.user)

        if "name" in attrs:
            attrs["name"] = (attrs["name"] or "").strip()
            if not attrs["name"]:
                raise serializers.ValidationError({"name": ["Name is required."]})

        if "url" in attrs:
            attrs["url"] = (attrs["url"] or "").strip()

        if "footer_group_id" in attrs:
            try:
                attrs["_footer_group"] = FooterGroup.objects.get(id=attrs["footer_group_id"], school=school)
            except FooterGroup.DoesNotExist:
                raise serializers.ValidationError(
                    {"footer_group_id": ["Selected footer group does not belong to your school."]}
                )

        return attrs

    def update(self, instance: FooterLink, validated_data: Dict[str, Any]) -> FooterLink:
        request = self.context["request"]

        if "name" in validated_data:
            instance.name = validated_data["name"]
        if "url" in validated_data:
            instance.url = validated_data["url"]
        if "_footer_group" in validated_data:
            instance.footer_group = validated_data["_footer_group"]

        instance.updated_by = request.user

        try:
            instance.full_clean()
            instance.save()
            return instance
        except DjangoValidationError as e:
            _raise_django_validation(e)


class FooterLinkReadSerializer(serializers.ModelSerializer):
    footer_group_id = serializers.UUIDField(source="footer_group.id", read_only=True)
    footer_group_name = serializers.CharField(source="footer_group.name", read_only=True)
    created_by_id = serializers.UUIDField(source="created_by.id", read_only=True, allow_null=True)
    updated_by_id = serializers.UUIDField(source="updated_by.id", read_only=True, allow_null=True)

    class Meta:
        model = FooterLink
        fields = [
            "id",
            "name",
            "url",
            "footer_group_id",
            "footer_group_name",
            "created_at",
            "created_by_id",
            "updated_at",
            "updated_by_id",
        ]

class FooterLinkCreateSerializer(serializers.Serializer):
    name = serializers.CharField(max_length=100)
    url = serializers.URLField(required=False, allow_blank=True, default="")
    footer_group_id = serializers.UUIDField()

    def validate(self, attrs: Dict[str, Any]) -> Dict[str, Any]:
        request = self.context["request"]
        school = get_school_for_user(request.user)

        name = (attrs.get("name") or "").strip()
        url = (attrs.get("url") or "").strip()
        footer_group_id = attrs.get("footer_group_id")

        if not name:
            raise serializers.ValidationError({"name": ["Name is required."]})

        try:
            footer_group = FooterGroup.objects.get(id=footer_group_id, school=school)
        except FooterGroup.DoesNotExist:
            raise serializers.ValidationError(
                {"footer_group_id": ["Selected footer group does not belong to your school."]}
            )

        attrs["name"] = name
        attrs["url"] = url
        attrs["_footer_group"] = footer_group
        return attrs

    def create(self, validated_data: Dict[str, Any]) -> FooterLink:
        request = self.context["request"]

        obj = FooterLink(
            name=validated_data["name"],
            url=validated_data.get("url", ""),
            footer_group=validated_data["_footer_group"],
            created_by=request.user,
            updated_by=request.user,
        )

        try:
            obj.full_clean()
            obj.save()
            return obj
        except DjangoValidationError as e:
            _raise_django_validation(e)


class FooterLinkUpdateSerializer(serializers.Serializer):
    name = serializers.CharField(max_length=100, required=False)
    url = serializers.URLField(required=False, allow_blank=True)
    footer_group_id = serializers.UUIDField(required=False)

    def validate(self, attrs: Dict[str, Any]) -> Dict[str, Any]:
        request = self.context["request"]
        school = get_school_for_user(request.user)

        if "name" in attrs:
            attrs["name"] = (attrs["name"] or "").strip()
            if not attrs["name"]:
                raise serializers.ValidationError({"name": ["Name is required."]})

        if "url" in attrs:
            attrs["url"] = (attrs["url"] or "").strip()

        if "footer_group_id" in attrs:
            try:
                attrs["_footer_group"] = FooterGroup.objects.get(id=attrs["footer_group_id"], school=school)
            except FooterGroup.DoesNotExist:
                raise serializers.ValidationError(
                    {"footer_group_id": ["Selected footer group does not belong to your school."]}
                )

        return attrs

    def update(self, instance: FooterLink, validated_data: Dict[str, Any]) -> FooterLink:
        request = self.context["request"]

        if "name" in validated_data:
            instance.name = validated_data["name"]
        if "url" in validated_data:
            instance.url = validated_data["url"]
        if "_footer_group" in validated_data:
            instance.footer_group = validated_data["_footer_group"]

        instance.updated_by = request.user

        try:
            instance.full_clean()
            instance.save()
            return instance
        except DjangoValidationError as e:
            _raise_django_validation(e)


class FooterLinkReadSerializer(serializers.ModelSerializer):
    footer_group_id = serializers.UUIDField(source="footer_group.id", read_only=True)
    footer_group_name = serializers.CharField(source="footer_group.name", read_only=True)
    created_by_id = serializers.UUIDField(source="created_by.id", read_only=True, allow_null=True)
    updated_by_id = serializers.UUIDField(source="updated_by.id", read_only=True, allow_null=True)

    class Meta:
        model = FooterLink
        fields = [
            "id",
            "name",
            "url",
            "footer_group_id",
            "footer_group_name",
            "created_at",
            "created_by_id",
            "updated_at",
            "updated_by_id",
        ]


class GalleryGroupCreateSerializer(serializers.Serializer):
    name = serializers.CharField(max_length=100)

    def validate(self, attrs: Dict[str, Any]) -> Dict[str, Any]:
        school = get_school_for_user(self.context["request"].user)
        name = (attrs.get("name") or "").strip()

        if not name:
            raise serializers.ValidationError({"name": ["Name is required."]})

        attrs["name"] = name
        attrs["_school"] = school
        return attrs

    def create(self, validated_data: Dict[str, Any]) -> GalleryGroup:
        request = self.context["request"]

        obj = GalleryGroup(
            name=validated_data["name"],
            school=validated_data["_school"],
            created_by=request.user,
            updated_by=request.user,
        )

        try:
            obj.full_clean()
            obj.save()
            return obj
        except DjangoValidationError as e:
            _raise_django_validation(e)


class GalleryGroupUpdateSerializer(serializers.Serializer):
    name = serializers.CharField(max_length=100, required=False)

    def validate(self, attrs: Dict[str, Any]) -> Dict[str, Any]:
        if "name" in attrs:
            attrs["name"] = (attrs["name"] or "").strip()
            if not attrs["name"]:
                raise serializers.ValidationError({"name": ["Name is required."]})
        return attrs

    def update(self, instance: GalleryGroup, validated_data: Dict[str, Any]) -> GalleryGroup:
        request = self.context["request"]

        if "name" in validated_data:
            instance.name = validated_data["name"]

        instance.updated_by = request.user

        try:
            instance.full_clean()
            instance.save()
            return instance
        except DjangoValidationError as e:
            _raise_django_validation(e)


class GalleryGroupReadSerializer(serializers.ModelSerializer):
    school_id = serializers.UUIDField(source="school.id", read_only=True, allow_null=True)
    created_by_id = serializers.UUIDField(source="created_by.id", read_only=True, allow_null=True)
    updated_by_id = serializers.UUIDField(source="updated_by.id", read_only=True, allow_null=True)

    class Meta:
        model = GalleryGroup
        fields = [
            "id",
            "name",
            "school_id",
            "created_at",
            "created_by_id",
            "updated_at",
            "updated_by_id",
        ]


class GalleryImageCreateSerializer(serializers.Serializer):
    image_id = serializers.UUIDField(required=False, allow_null=True)
    caption = serializers.CharField(max_length=255, required=False, allow_blank=True, default="")
    gallery_group_id = serializers.UUIDField()

    def validate(self, attrs: Dict[str, Any]) -> Dict[str, Any]:
        request = self.context["request"]
        school = get_school_for_user(request.user)

        caption = (attrs.get("caption") or "").strip()
        gallery_group_id = attrs.get("gallery_group_id")

        try:
            gallery_group = GalleryGroup.objects.get(id=gallery_group_id, school=school)
        except GalleryGroup.DoesNotExist:
            raise serializers.ValidationError(
                {"gallery_group_id": ["Selected gallery group does not belong to your school."]}
            )

        attrs["caption"] = caption
        attrs["_gallery_group"] = gallery_group
        return attrs

    def create(self, validated_data: Dict[str, Any]) -> GalleryImage:
        request = self.context["request"]

        obj = GalleryImage(
            image_id=validated_data.get("image_id"),
            caption=validated_data.get("caption", ""),
            gallery_group=validated_data["_gallery_group"],
            created_by=request.user,
            updated_by=request.user,
        )

        try:
            obj.full_clean()
            obj.save()
            return obj
        except DjangoValidationError as e:
            _raise_django_validation(e)


class GalleryImageUpdateSerializer(serializers.Serializer):
    image_id = serializers.UUIDField(required=False, allow_null=True)
    caption = serializers.CharField(max_length=255, required=False, allow_blank=True)
    gallery_group_id = serializers.UUIDField(required=False)

    def validate(self, attrs: Dict[str, Any]) -> Dict[str, Any]:
        request = self.context["request"]
        school = get_school_for_user(request.user)

        if "caption" in attrs:
            attrs["caption"] = (attrs["caption"] or "").strip()

        if "gallery_group_id" in attrs:
            try:
                attrs["_gallery_group"] = GalleryGroup.objects.get(id=attrs["gallery_group_id"], school=school)
            except GalleryGroup.DoesNotExist:
                raise serializers.ValidationError(
                    {"gallery_group_id": ["Selected gallery group does not belong to your school."]}
                )

        return attrs

    def update(self, instance: GalleryImage, validated_data: Dict[str, Any]) -> GalleryImage:
        request = self.context["request"]

        if "image_id" in validated_data:
            instance.image_id = validated_data["image_id"]
        if "caption" in validated_data:
            instance.caption = validated_data["caption"]
        if "_gallery_group" in validated_data:
            instance.gallery_group = validated_data["_gallery_group"]

        instance.updated_by = request.user

        try:
            instance.full_clean()
            instance.save()
            return instance
        except DjangoValidationError as e:
            _raise_django_validation(e)


class GalleryImageReadSerializer(serializers.ModelSerializer):
    image = UploadedFileSerializer(read_only=True)
    gallery_group_id = serializers.UUIDField(source="gallery_group.id", read_only=True)
    gallery_group_name = serializers.CharField(source="gallery_group.name", read_only=True)
    created_by_id = serializers.UUIDField(source="created_by.id", read_only=True, allow_null=True)
    updated_by_id = serializers.UUIDField(source="updated_by.id", read_only=True, allow_null=True)

    class Meta:
        model = GalleryImage
        fields = [
            "id",
            "image",
            "caption",
            "gallery_group_id",
            "gallery_group_name",
            "created_at",
            "created_by_id",
            "updated_at",
            "updated_by_id",
        ]