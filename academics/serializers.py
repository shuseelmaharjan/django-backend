# academics/serializers.py
from __future__ import annotations
from typing import Any, Dict, List
from uuid import UUID

from django.db import IntegrityError, transaction
from django.core.exceptions import ValidationError as DjangoValidationError
from rest_framework import serializers

from academics.models import AcademicClass, Section, StudentEnrollments
from batch.models import AcademicBatch
from accounts.models import User
from utils.get_school_id_by_token import get_school_for_user


def _raise_django_validation(e: DjangoValidationError):
    """
    Convert Django ValidationError to DRF ValidationError with message_dict if possible.
    """
    if hasattr(e, "message_dict"):
        raise serializers.ValidationError(e.message_dict)
    raise serializers.ValidationError({"detail": e.messages})


# ------------------------
# AcademicClass serializers
# ------------------------

class AcademicClassCreateSerializer(serializers.Serializer):
    batch_id = serializers.IntegerField()
    name = serializers.CharField(max_length=80)
    sort_order = serializers.IntegerField(required=False, default=0)
    is_active = serializers.BooleanField(required=False, default=True)

    def validate(self, attrs: Dict[str, Any]) -> Dict[str, Any]:
        request = self.context["request"]
        school = get_school_for_user(request.user)

        batch = AcademicBatch.objects.filter(id=attrs["batch_id"], school=school).first()
        if not batch:
            raise serializers.ValidationError({"batch_id": ["Invalid batch for your school."]})

        # ✅ only active batch can create
        if not batch.is_active:
            raise serializers.ValidationError({"batch_id": ["You can only create classrooms for an active batch."]})

        attrs["_batch"] = batch
        attrs["name"] = (attrs.get("name") or "").strip()
        if not attrs["name"]:
            raise serializers.ValidationError({"name": ["Name is required."]})

        return attrs

    def create(self, validated_data: Dict[str, Any]) -> AcademicClass:
        obj = AcademicClass(
            batch=validated_data["_batch"],
            name=validated_data["name"],
            sort_order=validated_data.get("sort_order", 0),
            is_active=validated_data.get("is_active", True),
        )

        try:
            obj.full_clean()
            obj.save()
            return obj
        except DjangoValidationError as e:
            _raise_django_validation(e)
        except IntegrityError:
            # unique constraint uq_batch_class_name
            raise serializers.ValidationError({"name": ["This class already exists in this batch."]})


class AcademicClassUpdateSerializer(serializers.Serializer):
    name = serializers.CharField(max_length=80, required=False)
    sort_order = serializers.IntegerField(required=False)
    is_active = serializers.BooleanField(required=False)

    def validate(self, attrs: Dict[str, Any]) -> Dict[str, Any]:
        if "name" in attrs:
            attrs["name"] = (attrs["name"] or "").strip()
            if not attrs["name"]:
                raise serializers.ValidationError({"name": ["Name is required."]})
        return attrs

    def update(self, instance: AcademicClass, validated_data: Dict[str, Any]) -> AcademicClass:
        # ✅ block edits if the batch is inactive (optional but consistent)
        if instance.batch and not instance.batch.is_active:
            raise serializers.ValidationError({"detail": "You can only modify classrooms in an active batch."})

        for f in ["name", "sort_order", "is_active"]:
            if f in validated_data:
                setattr(instance, f, validated_data[f])

        try:
            instance.full_clean()
            instance.save()
            return instance
        except DjangoValidationError as e:
            _raise_django_validation(e)
        except IntegrityError:
            raise serializers.ValidationError({"name": ["This class already exists in this batch."]})


class AcademicClassReadSerializer(serializers.ModelSerializer):
    batch_id = serializers.IntegerField(source="batch.id", read_only=True)
    school_id = serializers.UUIDField(source="batch.school.id", read_only=True)
    school_code = serializers.CharField(source="batch.school.code", read_only=True)

    class Meta:
        model = AcademicClass
        fields = [
            "id", "batch_id", "school_id", "school_code",
            "name", "sort_order", "is_active", "created_at"
        ]


class AcademicClassReorderSerializer(serializers.Serializer):
    batch_id = serializers.IntegerField()
    ordered_ids = serializers.ListField(
        child=serializers.UUIDField(),
        allow_empty=False,
        min_length=1,
    )

    def validate(self, attrs: Dict[str, Any]) -> Dict[str, Any]:
        request = self.context["request"]
        school = get_school_for_user(request.user)

        batch = AcademicBatch.objects.filter(id=attrs["batch_id"], school=school).first()
        if not batch:
            raise serializers.ValidationError({"batch_id": ["Invalid batch for your school."]})

        # ✅ reorder only for active batch
        if not batch.is_active:
            raise serializers.ValidationError({"batch_id": ["You can only reorder classrooms for an active batch."]})

        ids: List[UUID] = attrs["ordered_ids"]
        if len(ids) != len(set(ids)):
            raise serializers.ValidationError({"ordered_ids": ["Duplicate IDs are not allowed."]})

        existing = set(
            AcademicClass.objects.filter(batch=batch, id__in=ids).values_list("id", flat=True)
        )
        missing = [str(x) for x in ids if x not in existing]
        if missing:
            raise serializers.ValidationError({"ordered_ids": [f"These IDs are not in this batch: {missing}"]})

        attrs["_batch"] = batch
        return attrs

    def save(self) -> Dict[str, Any]:
        batch = self.validated_data["_batch"]
        ids: List[UUID] = self.validated_data["ordered_ids"]

        with transaction.atomic():
            rows = list(
                AcademicClass.objects.select_for_update().filter(batch=batch, id__in=ids)
            )
            row_map = {r.id: r for r in rows}

            to_update = []
            for idx, cid in enumerate(ids):
                r = row_map[cid]
                r.sort_order = idx
                to_update.append(r)

            AcademicClass.objects.bulk_update(to_update, ["sort_order"])

        return {"updated": len(ids)}


# ------------------------
# Section serializers
# ------------------------

class SectionCreateSerializer(serializers.Serializer):
    academic_class_id = serializers.UUIDField()
    name = serializers.CharField(max_length=30)
    sort_order = serializers.IntegerField(required=False, default=0)
    is_active = serializers.BooleanField(required=False, default=True)

    def validate(self, attrs: Dict[str, Any]) -> Dict[str, Any]:
        request = self.context["request"]
        school = get_school_for_user(request.user)

        academic_class = (
            AcademicClass.objects.select_related("batch__school")
            .filter(id=attrs["academic_class_id"], batch__school=school)
            .first()
        )
        if not academic_class:
            raise serializers.ValidationError({"academic_class_id": ["Invalid class for your school."]})

        # ✅ only active batch can create sections
        if academic_class.batch and not academic_class.batch.is_active:
            raise serializers.ValidationError({"academic_class_id": ["You can only create sections in an active batch."]})

        attrs["_academic_class"] = academic_class
        attrs["name"] = (attrs.get("name") or "").strip()
        if not attrs["name"]:
            raise serializers.ValidationError({"name": ["Name is required."]})

        return attrs

    def create(self, validated_data: Dict[str, Any]) -> Section:
        obj = Section(
            academic_class=validated_data["_academic_class"],
            name=validated_data["name"],
            sort_order=validated_data.get("sort_order", 0),
            is_active=validated_data.get("is_active", True),
        )

        try:
            obj.full_clean()
            obj.save()
            return obj
        except DjangoValidationError as e:
            _raise_django_validation(e)
        except IntegrityError:
            raise serializers.ValidationError({"name": ["This section already exists in this class."]})


class SectionUpdateSerializer(serializers.Serializer):
    name = serializers.CharField(max_length=30, required=False)
    sort_order = serializers.IntegerField(required=False)
    is_active = serializers.BooleanField(required=False)

    def validate(self, attrs: Dict[str, Any]) -> Dict[str, Any]:
        if "name" in attrs:
            attrs["name"] = (attrs["name"] or "").strip()
            if not attrs["name"]:
                raise serializers.ValidationError({"name": ["Name is required."]})
        return attrs

    def update(self, instance: Section, validated_data: Dict[str, Any]) -> Section:
        if instance.academic_class.batch and not instance.academic_class.batch.is_active:
            raise serializers.ValidationError({"detail": "You can only modify sections in an active batch."})

        for f in ["name", "sort_order", "is_active"]:
            if f in validated_data:
                setattr(instance, f, validated_data[f])

        try:
            instance.full_clean()
            instance.save()
            return instance
        except DjangoValidationError as e:
            _raise_django_validation(e)
        except IntegrityError:
            raise serializers.ValidationError({"name": ["This section already exists in this class."]})


class SectionReadSerializer(serializers.ModelSerializer):
    academic_class_id = serializers.UUIDField(source="academic_class.id", read_only=True)
    batch_id = serializers.IntegerField(source="academic_class.batch.id", read_only=True)

    class Meta:
        model = Section
        fields = [
            "id", "academic_class_id", "batch_id",
            "name", "sort_order", "is_active", "created_at"
        ]


class SectionReorderSerializer(serializers.Serializer):
    academic_class_id = serializers.UUIDField()
    ordered_ids = serializers.ListField(
        child=serializers.UUIDField(),
        allow_empty=False,
        min_length=1,
    )

    def validate(self, attrs: Dict[str, Any]) -> Dict[str, Any]:
        request = self.context["request"]
        school = get_school_for_user(request.user)

        academic_class = (
            AcademicClass.objects.select_related("batch__school")
            .filter(id=attrs["academic_class_id"], batch__school=school)
            .first()
        )
        if not academic_class:
            raise serializers.ValidationError({"academic_class_id": ["Invalid class for your school."]})

        # ✅ reorder only for active batch
        if academic_class.batch and not academic_class.batch.is_active:
            raise serializers.ValidationError({"academic_class_id": ["You can only reorder sections in an active batch."]})

        ids = attrs["ordered_ids"]
        if len(ids) != len(set(ids)):
            raise serializers.ValidationError({"ordered_ids": ["Duplicate IDs are not allowed."]})

        existing = set(
            Section.objects.filter(academic_class=academic_class, id__in=ids).values_list("id", flat=True)
        )
        missing = [str(x) for x in ids if x not in existing]
        if missing:
            raise serializers.ValidationError({"ordered_ids": [f"These IDs are not in this class: {missing}"]})

        attrs["_academic_class"] = academic_class
        return attrs

    def save(self) -> Dict[str, Any]:
        academic_class = self.validated_data["_academic_class"]
        ids: List[UUID] = self.validated_data["ordered_ids"]

        with transaction.atomic():
            rows = list(
                Section.objects.select_for_update().filter(academic_class=academic_class, id__in=ids)
            )
            row_map = {r.id: r for r in rows}

            to_update = []
            for idx, sid in enumerate(ids):
                r = row_map[sid]
                r.sort_order = idx
                to_update.append(r)

            Section.objects.bulk_update(to_update, ["sort_order"])

        return {"updated": len(ids)}


class StudentEnrollmentCreateSerializer(serializers.Serializer):
    batch_id = serializers.IntegerField()
    student_id = serializers.UUIDField()
    academic_class_id = serializers.UUIDField()
    section_id = serializers.UUIDField(required=False, allow_null=True)
    status = serializers.ChoiceField(
        choices=[c[0] for c in StudentEnrollments._meta.get_field("status").choices],
        required=False,
    )

    def validate(self, attrs: Dict[str, Any]) -> Dict[str, Any]:
        request = self.context["request"]
        school = get_school_for_user(request.user)

        batch = AcademicBatch.objects.filter(id=attrs["batch_id"], school=school).first()
        if not batch:
            raise serializers.ValidationError({"batch_id": ["Invalid batch for your school."]})
        if not batch.is_active:
            raise serializers.ValidationError({"batch_id": ["You can only enroll students in an active batch."]})

        academic_class = (
            AcademicClass.objects.select_related("batch__school")
            .filter(id=attrs["academic_class_id"], batch__school=school)
            .first()
        )
        if not academic_class:
            raise serializers.ValidationError({"academic_class_id": ["Invalid class for your school."]})

        if academic_class.batch_id != batch.id:
            raise serializers.ValidationError({"academic_class_id": ["Class does not belong to the selected batch."]})

        # Student must belong to school (adjust field if your User has school relation differently)
        student = User.objects.filter(id=attrs["student_id"], school=school).first()
        if not student:
            raise serializers.ValidationError({"student_id": ["Invalid student for your school."]})

        section = None
        if attrs.get("section_id"):
            section = (
                Section.objects.select_related("academic_class__batch__school")
                .filter(id=attrs["section_id"], academic_class__batch__school=school)
                .first()
            )
            if not section:
                raise serializers.ValidationError({"section_id": ["Invalid section for your school."]})
            if section.academic_class_id != academic_class.id:
                raise serializers.ValidationError({"section_id": ["Section must belong to the selected class."]})

        attrs["_batch"] = batch
        attrs["_academic_class"] = academic_class
        attrs["_student"] = student
        attrs["_section"] = section
        return attrs

    def create(self, validated_data: Dict[str, Any]) -> StudentEnrollments:
        obj = StudentEnrollments(
            batch=validated_data["_batch"],
            student=validated_data["_student"],
            academic_class=validated_data["_academic_class"],
            section=validated_data["_section"],
            status=validated_data.get("status") or StudentEnrollments._meta.get_field("status").default,
        )
        try:
            obj.full_clean()
            obj.save()
            return obj
        except DjangoValidationError as e:
            _raise_django_validation(e)
        except IntegrityError:
            # Could be either uq_batch_student_class_enrollment or uq_batch_student_section_enrollment
            raise serializers.ValidationError({"detail": "Duplicate enrollment for this student."})


class StudentEnrollmentUpdateSerializer(serializers.Serializer):
    academic_class_id = serializers.UUIDField(required=False)
    section_id = serializers.UUIDField(required=False, allow_null=True)
    status = serializers.ChoiceField(
        choices=[c[0] for c in StudentEnrollments._meta.get_field("status").choices],
        required=False,
    )

    def validate(self, attrs: Dict[str, Any]) -> Dict[str, Any]:
        request = self.context["request"]
        school = get_school_for_user(request.user)

        instance: StudentEnrollments = self.instance

        # Block updates if batch inactive
        if instance.batch and not instance.batch.is_active:
            raise serializers.ValidationError({"detail": "You can only modify enrollments in an active batch."})

        academic_class = instance.academic_class
        section = instance.section

        # If class is changing, validate ownership + batch match
        if "academic_class_id" in attrs:
            academic_class = (
                AcademicClass.objects.select_related("batch__school")
                .filter(id=attrs["academic_class_id"], batch__school=school)
                .first()
            )
            if not academic_class:
                raise serializers.ValidationError({"academic_class_id": ["Invalid class for your school."]})
            if academic_class.batch_id != instance.batch_id:
                raise serializers.ValidationError({"academic_class_id": ["Class does not belong to this enrollment batch."]})

        # If section is provided (or null), validate it
        if "section_id" in attrs:
            if attrs["section_id"] is None:
                section = None
            else:
                section = (
                    Section.objects.select_related("academic_class__batch__school")
                    .filter(id=attrs["section_id"], academic_class__batch__school=school)
                    .first()
                )
                if not section:
                    raise serializers.ValidationError({"section_id": ["Invalid section for your school."]})
                if section.academic_class_id != academic_class.id:
                    raise serializers.ValidationError({"section_id": ["Section must belong to the selected class."]})

        attrs["_academic_class"] = academic_class
        attrs["_section"] = section
        return attrs

    def update(self, instance: StudentEnrollments, validated_data: Dict[str, Any]) -> StudentEnrollments:
        if "_academic_class" in validated_data:
            instance.academic_class = validated_data["_academic_class"]
        if "_section" in validated_data:
            instance.section = validated_data["_section"]
        if "status" in validated_data:
            instance.status = validated_data["status"]

        try:
            instance.full_clean()
            instance.save()
            return instance
        except DjangoValidationError as e:
            _raise_django_validation(e)
        except IntegrityError:
            raise serializers.ValidationError({"detail": "Duplicate enrollment for this student."})


class StudentEnrollmentReadSerializer(serializers.ModelSerializer):
    batch_id = serializers.IntegerField(source="batch.id", read_only=True)
    academic_class_id = serializers.UUIDField(source="academic_class.id", read_only=True)
    section_id = serializers.UUIDField(source="section.id", read_only=True, allow_null=True)
    student_id = serializers.UUIDField(source="student.id", read_only=True)

    class Meta:
        model = StudentEnrollments
        fields = [
            "id",
            "batch_id",
            "student_id",
            "academic_class_id",
            "section_id",
            "enrolled_at",
            "status",
        ]