# academics/serializers.py
from __future__ import annotations
from typing import Any, Dict, Optional, List
from uuid import UUID

from django.db import IntegrityError, transaction
from django.core.exceptions import ValidationError as DjangoValidationError
from django.db.models import Q
from rest_framework import serializers
from common.constants import UserRole, UserStatus
from subjects.models import Subject
from academics.models import AcademicClass, Section, StudentEnrollments, Schedule, ScheduleKind
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


# ------------------------
# Schedule serializers
# ------------------------
def _has_overlap(qs, *, day_of_week: int, start_time, end_time, exclude_id=None) -> bool:
    """
    Overlap rule:
      existing.start < new.end AND existing.end > new.start
    """
    q = qs.filter(
        day_of_week=day_of_week,
        start_time__lt=end_time,
        end_time__gt=start_time,
    )
    if exclude_id:
        q = q.exclude(id=exclude_id)
    return q.exists()


def _scope_filter_for_class_section(*, academic_class, section):
    """
    Section wildcard logic:
      - If existing.section is NULL => applies to all sections of that class
      - If new section is NULL => should match any section of that class
    """
    if academic_class is None:
        # batch-wide block (class is null): match only other batch-wide blocks
        return Q(academic_class__isnull=True, section__isnull=True)

    if section is None:
        # new row applies to whole class => conflicts with any section row of that class OR class-wide row
        return Q(academic_class=academic_class)
    else:
        # new row applies to a specific section => conflicts with same section OR class-wide row
        return Q(academic_class=academic_class) & (Q(section=section) | Q(section__isnull=True))


def _scope_filter_for_batchwide_or_class(*, academic_class, section):
    """
    If there exists a batch-wide break/holiday (academic_class NULL),
    it should block everything in the batch too.

    So when creating/updating a CLASS row, we also want to check overlaps against:
      - batch-wide blockers (class NULL)
      - relevant class/section blockers
    """
    batchwide = Q(academic_class__isnull=True, section__isnull=True)
    class_scope = _scope_filter_for_class_section(academic_class=academic_class, section=section)
    return batchwide | class_scope


class ScheduleCreateSerializer(serializers.Serializer):
    batch_id = serializers.IntegerField()

    # scope
    academic_class_id = serializers.UUIDField(required=False, allow_null=True)
    section_id = serializers.UUIDField(required=False, allow_null=True)

    # only for class
    subject_id = serializers.UUIDField(required=False, allow_null=True)
    teacher_id = serializers.UUIDField(required=False, allow_null=True)

    kind = serializers.ChoiceField(choices=ScheduleKind.choices, required=False)
    title = serializers.CharField(required=False, allow_blank=True)

    day_of_week = serializers.IntegerField(min_value=0, max_value=6)
    start_time = serializers.TimeField()
    end_time = serializers.TimeField()

    def validate(self, attrs: Dict[str, Any]) -> Dict[str, Any]:
        request = self.context["request"]
        school = get_school_for_user(request.user)

        kind = attrs.get("kind") or ScheduleKind.CLASS

        # ---- time sanity
        if attrs["end_time"] <= attrs["start_time"]:
            raise serializers.ValidationError({"end_time": ["End time must be after start time."]})

        # ---- batch (school scoped)
        batch = AcademicBatch.objects.filter(id=attrs["batch_id"], school=school).first()
        if not batch:
            raise serializers.ValidationError({"batch_id": ["Invalid batch for your school."]})
        if hasattr(batch, "is_active") and not batch.is_active:
            raise serializers.ValidationError({"batch_id": ["You can only create schedules for an active batch."]})

        # ---- scope: academic_class/section (optional for batch-wide breaks/holidays)
        academic_class = None
        if "academic_class_id" in attrs and attrs["academic_class_id"] is not None:
            academic_class = (
                AcademicClass.objects
                .select_related("batch__school")
                .filter(id=attrs["academic_class_id"], batch__school=school)
                .first()
            )
            if not academic_class:
                raise serializers.ValidationError({"academic_class_id": ["Invalid class for your school."]})
            if academic_class.batch_id != batch.id:
                raise serializers.ValidationError({"academic_class_id": ["Class does not belong to the selected batch."]})

        section = None
        if "section_id" in attrs and attrs["section_id"] is not None:
            if not academic_class:
                raise serializers.ValidationError({"section_id": ["Section requires academic_class."]})
            section = (
                Section.objects
                .select_related("academic_class__batch__school")
                .filter(id=attrs["section_id"], academic_class__batch__school=school)
                .first()
            )
            if not section:
                raise serializers.ValidationError({"section_id": ["Invalid section for your school."]})
            if section.academic_class_id != academic_class.id:
                raise serializers.ValidationError({"section_id": ["Section must belong to the selected class."]})

        # ---- kind-based requirements
        subject = None
        teacher = None

        if kind == ScheduleKind.CLASS:
            if not academic_class:
                raise serializers.ValidationError({"academic_class_id": ["academic_class is required for class schedules."]})

            # subject required
            if not attrs.get("subject_id"):
                raise serializers.ValidationError({"subject_id": ["This field is required for class schedules."]})
            subject = Subject.objects.filter(id=attrs["subject_id"], status="active").first()
            if not subject:
                raise serializers.ValidationError({"subject_id": ["Invalid/Inactive subject."]})

            # teacher required
            if not attrs.get("teacher_id"):
                raise serializers.ValidationError({"teacher_id": ["This field is required for class schedules."]})
            teacher = (
                User.objects
                .select_related("profile")
                .filter(
                    id=attrs["teacher_id"],
                    role=UserRole.TEACHER,
                    status=UserStatus.ACTIVE,
                    is_deleted=False,
                    profile__school=school,
                )
                .first()
            )
            if not teacher:
                raise serializers.ValidationError({"teacher_id": ["Invalid teacher for your school."]})

        else:
            # BREAK/HOLIDAY
            # Force subject/teacher to be empty
            if attrs.get("subject_id") is not None:
                raise serializers.ValidationError({"subject_id": ["Subject is not allowed for break/holiday schedules."]})
            if attrs.get("teacher_id") is not None:
                raise serializers.ValidationError({"teacher_id": ["Teacher is not allowed for break/holiday schedules."]})

            # Optional: you can require academic_class for break/holiday by uncommenting:
            # if not academic_class:
            #     raise serializers.ValidationError({"academic_class_id": ["academic_class is required for break/holiday schedules."]})

        # ---- conflict checks
        base_qs = Schedule.objects.filter(batch=batch)

        # 1) teacher conflict: only CLASS rows should conflict with teacher
        if kind == ScheduleKind.CLASS:
            if _has_overlap(
                base_qs.filter(kind=ScheduleKind.CLASS, teacher=teacher),
                day_of_week=attrs["day_of_week"],
                start_time=attrs["start_time"],
                end_time=attrs["end_time"],
            ):
                raise serializers.ValidationError({"teacher_id": ["Teacher has another class at this time."]})

        # 2) scope conflict:
        # CLASS must not overlap with CLASS/BREAK/HOLIDAY blockers (including batch-wide blockers)
        # BREAK/HOLIDAY must not overlap with ANYTHING in that scope (to avoid messy data)
        if kind == ScheduleKind.CLASS:
            scope_q = _scope_filter_for_batchwide_or_class(academic_class=academic_class, section=section)
            if _has_overlap(
                base_qs.filter(scope_q).filter(kind__in=[ScheduleKind.CLASS, ScheduleKind.BREAK, ScheduleKind.HOLIDAY]),
                day_of_week=attrs["day_of_week"],
                start_time=attrs["start_time"],
                end_time=attrs["end_time"],
            ):
                raise serializers.ValidationError({"detail": "Time is blocked by another class/break/holiday."})
        else:
            scope_q = _scope_filter_for_batchwide_or_class(academic_class=academic_class, section=section)
            if _has_overlap(
                base_qs.filter(scope_q),
                day_of_week=attrs["day_of_week"],
                start_time=attrs["start_time"],
                end_time=attrs["end_time"],
            ):
                raise serializers.ValidationError({"detail": "Break/Holiday overlaps an existing schedule block."})

        attrs["_batch"] = batch
        attrs["_academic_class"] = academic_class
        attrs["_section"] = section
        attrs["_subject"] = subject
        attrs["_teacher"] = teacher
        attrs["_kind"] = kind
        attrs["_title"] = attrs.get("title", "") or ""
        return attrs

    def create(self, validated_data: Dict[str, Any]) -> Schedule:
        obj = Schedule(
            batch=validated_data["_batch"],
            academic_class=validated_data["_academic_class"],
            section=validated_data["_section"],
            subject=validated_data["_subject"],
            teacher=validated_data["_teacher"],
            kind=validated_data["_kind"],
            title=validated_data["_title"],
            day_of_week=validated_data["day_of_week"],
            start_time=validated_data["start_time"],
            end_time=validated_data["end_time"],
        )
        try:
            obj.full_clean()
            obj.save()
            return obj
        except DjangoValidationError as e:
            _raise_django_validation(e)
        except IntegrityError:
            raise serializers.ValidationError({"detail": "Failed to create schedule."})


class ScheduleUpdateSerializer(serializers.Serializer):
    batch_id = serializers.IntegerField(required=False)

    academic_class_id = serializers.UUIDField(required=False, allow_null=True)
    section_id = serializers.UUIDField(required=False, allow_null=True)

    subject_id = serializers.UUIDField(required=False, allow_null=True)
    teacher_id = serializers.UUIDField(required=False, allow_null=True)

    kind = serializers.ChoiceField(choices=ScheduleKind.choices, required=False)
    title = serializers.CharField(required=False, allow_blank=True)

    day_of_week = serializers.IntegerField(required=False, min_value=0, max_value=6)
    start_time = serializers.TimeField(required=False)
    end_time = serializers.TimeField(required=False)

    def validate(self, attrs: Dict[str, Any]) -> Dict[str, Any]:
        request = self.context["request"]
        school = get_school_for_user(request.user)
        instance: Schedule = self.instance

        # resolve current values
        batch = instance.batch
        academic_class = instance.academic_class
        section = instance.section
        subject = instance.subject
        teacher = instance.teacher
        kind = attrs.get("kind", instance.kind)
        title = attrs.get("title", instance.title)

        day = attrs.get("day_of_week", instance.day_of_week)
        start = attrs.get("start_time", instance.start_time)
        end = attrs.get("end_time", instance.end_time)

        if end <= start:
            raise serializers.ValidationError({"end_time": ["End time must be after start time."]})

        # batch change
        if "batch_id" in attrs:
            batch = AcademicBatch.objects.filter(id=attrs["batch_id"], school=school).first()
            if not batch:
                raise serializers.ValidationError({"batch_id": ["Invalid batch for your school."]})
            if hasattr(batch, "is_active") and not batch.is_active:
                raise serializers.ValidationError({"batch_id": ["You can only modify schedules in an active batch."]})

        # class change (nullable allowed for batch-wide blocks)
        if "academic_class_id" in attrs:
            if attrs["academic_class_id"] is None:
                academic_class = None
                section = None  # section must be null if class is null
            else:
                academic_class = (
                    AcademicClass.objects
                    .select_related("batch__school")
                    .filter(id=attrs["academic_class_id"], batch__school=school)
                    .first()
                )
                if not academic_class:
                    raise serializers.ValidationError({"academic_class_id": ["Invalid class for your school."]})
                if academic_class.batch_id != batch.id:
                    raise serializers.ValidationError({"academic_class_id": ["Class does not belong to the selected batch."]})

        # section change (explicit null allowed)
        if "section_id" in attrs:
            if attrs["section_id"] is None:
                section = None
            else:
                if not academic_class:
                    raise serializers.ValidationError({"section_id": ["Section requires academic_class."]})
                section = (
                    Section.objects
                    .select_related("academic_class__batch__school")
                    .filter(id=attrs["section_id"], academic_class__batch__school=school)
                    .first()
                )
                if not section:
                    raise serializers.ValidationError({"section_id": ["Invalid section for your school."]})
                if section.academic_class_id != academic_class.id:
                    raise serializers.ValidationError({"section_id": ["Section must belong to the selected class."]})

        # kind-based requirements + subject/teacher changes
        if kind == ScheduleKind.CLASS:
            if not academic_class:
                raise serializers.ValidationError({"academic_class_id": ["academic_class is required for class schedules."]})

            # subject
            if "subject_id" in attrs:
                if attrs["subject_id"] is None:
                    raise serializers.ValidationError({"subject_id": ["This field cannot be null for class schedules."]})
                subject = Subject.objects.filter(id=attrs["subject_id"], status="active").first()
                if not subject:
                    raise serializers.ValidationError({"subject_id": ["Invalid/Inactive subject."]})
            elif subject is None:
                raise serializers.ValidationError({"subject_id": ["Subject is required for class schedules."]})

            # teacher
            if "teacher_id" in attrs:
                if attrs["teacher_id"] is None:
                    raise serializers.ValidationError({"teacher_id": ["This field cannot be null for class schedules."]})
                teacher = (
                    User.objects
                    .select_related("profile")
                    .filter(
                        id=attrs["teacher_id"],
                        role=UserRole.TEACHER,
                        status=UserStatus.ACTIVE,
                        is_deleted=False,
                        profile__school=school,
                    )
                    .first()
                )
                if not teacher:
                    raise serializers.ValidationError({"teacher_id": ["Invalid teacher for your school."]})
            elif teacher is None:
                raise serializers.ValidationError({"teacher_id": ["Teacher is required for class schedules."]})

        else:
            # BREAK/HOLIDAY: subject/teacher must be null
            if "subject_id" in attrs and attrs["subject_id"] is not None:
                raise serializers.ValidationError({"subject_id": ["Subject is not allowed for break/holiday schedules."]})
            if "teacher_id" in attrs and attrs["teacher_id"] is not None:
                raise serializers.ValidationError({"teacher_id": ["Teacher is not allowed for break/holiday schedules."]})

            subject = None
            teacher = None

        # ---- conflict checks
        base_qs = Schedule.objects.filter(batch=batch)

        # teacher overlap only for CLASS
        if kind == ScheduleKind.CLASS:
            if _has_overlap(
                base_qs.filter(kind=ScheduleKind.CLASS, teacher=teacher),
                day_of_week=day,
                start_time=start,
                end_time=end,
                exclude_id=instance.id,
            ):
                raise serializers.ValidationError({"teacher_id": ["Teacher has another class at this time."]})

        # scope overlaps
        if kind == ScheduleKind.CLASS:
            scope_q = _scope_filter_for_batchwide_or_class(academic_class=academic_class, section=section)
            if _has_overlap(
                base_qs.filter(scope_q).filter(kind__in=[ScheduleKind.CLASS, ScheduleKind.BREAK, ScheduleKind.HOLIDAY]),
                day_of_week=day,
                start_time=start,
                end_time=end,
                exclude_id=instance.id,
            ):
                raise serializers.ValidationError({"detail": "Time is blocked by another class/break/holiday."})
        else:
            scope_q = _scope_filter_for_batchwide_or_class(academic_class=academic_class, section=section)
            if _has_overlap(
                base_qs.filter(scope_q),
                day_of_week=day,
                start_time=start,
                end_time=end,
                exclude_id=instance.id,
            ):
                raise serializers.ValidationError({"detail": "Break/Holiday overlaps an existing schedule block."})

        attrs["_batch"] = batch
        attrs["_academic_class"] = academic_class
        attrs["_section"] = section
        attrs["_subject"] = subject
        attrs["_teacher"] = teacher
        attrs["_kind"] = kind
        attrs["_title"] = title or ""

        attrs["_day"] = day
        attrs["_start"] = start
        attrs["_end"] = end
        return attrs

    def update(self, instance: Schedule, validated_data: Dict[str, Any]) -> Schedule:
        instance.batch = validated_data["_batch"]
        instance.academic_class = validated_data["_academic_class"]
        instance.section = validated_data["_section"]
        instance.subject = validated_data["_subject"]
        instance.teacher = validated_data["_teacher"]
        instance.kind = validated_data["_kind"]
        instance.title = validated_data["_title"]
        instance.day_of_week = validated_data["_day"]
        instance.start_time = validated_data["_start"]
        instance.end_time = validated_data["_end"]

        try:
            instance.full_clean()
            instance.save()
            return instance
        except DjangoValidationError as e:
            _raise_django_validation(e)
        except IntegrityError:
            raise serializers.ValidationError({"detail": "Failed to update schedule."})


class ScheduleReadSerializer(serializers.ModelSerializer):
    batch_id = serializers.IntegerField(source="batch.id", read_only=True)

    academic_class_id = serializers.UUIDField(source="academic_class.id", read_only=True, allow_null=True)
    academic_class_name = serializers.CharField(source="academic_class.name", read_only=True, allow_null=True)

    section_id = serializers.UUIDField(source="section.id", read_only=True, allow_null=True)
    section_name = serializers.CharField(source="section.name", read_only=True, allow_null=True)

    subject_id = serializers.UUIDField(source="subject.id", read_only=True, allow_null=True)
    subject_name = serializers.CharField(source="subject.name", read_only=True, allow_null=True)
    subject_code = serializers.CharField(source="subject.code", read_only=True, allow_null=True)

    teacher_id = serializers.UUIDField(source="teacher.id", read_only=True, allow_null=True)
    teacher_name = serializers.SerializerMethodField()

    class Meta:
        model = Schedule
        fields = [
            "id",
            "batch_id",
            "kind",
            "title",
            "academic_class_id",
            "academic_class_name",
            "section_id",
            "section_name",
            "subject_id",
            "subject_name",
            "subject_code",
            "teacher_id",
            "teacher_name",
            "day_of_week",
            "start_time",
            "end_time",
        ]

    def get_teacher_name(self, obj: Schedule) -> Optional[str]:
        if not obj.teacher_id:
            return None
        fn = getattr(obj.teacher, "get_full_name", None)
        return fn() if callable(fn) else f"{obj.teacher.first_name} {obj.teacher.last_name}".strip()


class ScheduleReadSerializer(serializers.ModelSerializer):
    batch_id = serializers.IntegerField(source="batch.id", read_only=True)

    academic_class_id = serializers.UUIDField(source="academic_class.id", read_only=True, allow_null=True)
    academic_class_name = serializers.CharField(source="academic_class.name", read_only=True, allow_null=True)

    section_id = serializers.UUIDField(source="section.id", read_only=True, allow_null=True)
    section_name = serializers.CharField(source="section.name", read_only=True, allow_null=True)

    subject_id = serializers.UUIDField(source="subject.id", read_only=True, allow_null=True)
    subject_name = serializers.CharField(source="subject.name", read_only=True, allow_null=True)
    subject_code = serializers.CharField(source="subject.code", read_only=True, allow_null=True)

    teacher_id = serializers.UUIDField(source="teacher.id", read_only=True, allow_null=True)
    teacher_name = serializers.SerializerMethodField()

    class Meta:
        model = Schedule
        fields = [
            "id",
            "batch_id",

            "kind",
            "title",

            "academic_class_id",
            "academic_class_name",

            "section_id",
            "section_name",

            "subject_id",
            "subject_name",
            "subject_code",

            "teacher_id",
            "teacher_name",

            "day_of_week",
            "start_time",
            "end_time",
        ]

    def get_teacher_name(self, obj: Schedule) -> Optional[str]:
        if not obj.teacher_id:
            return None
        fn = getattr(obj.teacher, "get_full_name", None)
        if callable(fn):
            return fn()
        return f"{obj.teacher.first_name} {obj.teacher.last_name}".strip()