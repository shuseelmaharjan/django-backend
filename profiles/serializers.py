from __future__ import annotations
from rest_framework import serializers
from .models import TeacherLevel, TeacherLevelStatus, TeacherSpecialization
from subjects.models import Subject
from accounts.models import User
from django.db import transaction
from common.constants import UserStatus, UserRole


class TeacherLevelReadSerializer(serializers.ModelSerializer):
    class Meta:
        model = TeacherLevel
        fields = ["id", "level", "status"]


class TeacherLevelCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = TeacherLevel
        fields = ["level", "status"]

    def validate_level(self, value: str):
        v = (value or "").strip()
        if not v:
            raise serializers.ValidationError("Level is required.")

        qs = TeacherLevel.objects.filter(level__iexact=v)

        if "DELETED" in TeacherLevelStatus.__members__:
            qs = qs.exclude(status=TeacherLevelStatus.DELETED)

        if qs.exists():
            raise serializers.ValidationError("Teacher level already exists.")

        return v

    def validate_status(self, value: str):
        if value not in TeacherLevelStatus.values:
            raise serializers.ValidationError("Invalid status.")
        return value


class TeacherLevelUpdateSerializer(serializers.ModelSerializer):
    class Meta:
        model = TeacherLevel
        fields = ["level", "status"]

    def validate_level(self, value: str):
        v = (value or "").strip()
        if not v:
            raise serializers.ValidationError("Level is required.")

        qs = TeacherLevel.objects.filter(level__iexact=v).exclude(pk=self.instance.pk)

        if "DELETED" in TeacherLevelStatus.__members__:
            qs = qs.exclude(status=TeacherLevelStatus.DELETED)

        if qs.exists():
            raise serializers.ValidationError("Teacher level already exists.")

        return v

    def validate_status(self, value: str):
        if value not in TeacherLevelStatus.values:
            raise serializers.ValidationError("Invalid status.")
        return value



class TeacherSpecializationReadSerializer(serializers.ModelSerializer):
    user = serializers.UUIDField(source="user_id", read_only=True)
    teacher_level = serializers.UUIDField(source="teacher_level_id", allow_null=True, read_only=True)
    subjects = serializers.SerializerMethodField()

    def get_subjects(self, obj: TeacherSpecialization):
        # return subject ids (lightweight)
        return [str(s.id) for s in obj.subjects.all()]

    class Meta:
        model = TeacherSpecialization
        fields = ["id", "user", "teacher_level", "subjects"]


class TeacherSpecializationWriteSerializer(serializers.Serializer):
    """
    Write payload:
    {
      "user": "<uuid>",
      "teacher_level": "<uuid or null>",
      "subjects": ["<uuid>", "<uuid>", ...]
    }
    """
    user = serializers.UUIDField()
    teacher_level = serializers.UUIDField(required=False, allow_null=True)
    subjects = serializers.ListField(
        child=serializers.UUIDField(),
        allow_empty=True,
        required=False,
        default=list,
    )

    def validate_user(self, value):
        try:
            user = User.objects.get(id=value, is_deleted=False)
        except User.DoesNotExist:
            raise serializers.ValidationError("User not found.")

        if user.role != UserRole.TEACHER and user.role != "teacher":
            raise serializers.ValidationError("Only teacher users can be specialized.")

        if user.status != UserStatus.DRAFT and user.status != "draft":
            raise serializers.ValidationError("User must be in DRAFT status to create specialization.")

        # attach user instance for later use
        self.context["_user_obj"] = user
        return value

    def validate_teacher_level(self, value):
        if value is None:
            return None
        if not TeacherLevel.objects.filter(id=value).exists():
            raise serializers.ValidationError("Teacher level not found.")
        return value

    def validate_subjects(self, value):
        ids = list(dict.fromkeys(value or []))  # de-duplicate, keep order
        if not ids:
            return []
        found = set(Subject.objects.filter(id__in=ids).values_list("id", flat=True))
        missing = [str(x) for x in ids if x not in found]
        if missing:
            raise serializers.ValidationError({"missing_subject_ids": missing})
        return ids

    @transaction.atomic
    def create(self, validated_data):
        user_id = validated_data["user"]
        teacher_level_id = validated_data.get("teacher_level", None)
        subject_ids = validated_data.get("subjects", [])

        user: User = self.context.get("_user_obj") or User.objects.select_for_update().get(id=user_id)

        user.refresh_from_db()
        if str(user.status).lower() != "draft":
            raise serializers.ValidationError({"user": ["User is not in DRAFT status."]})
        if str(user.role).lower() != "teacher":
            raise serializers.ValidationError({"user": ["Only teacher users are allowed."]})

        if TeacherSpecialization.objects.filter(user_id=user_id).exists():
            raise serializers.ValidationError({"user": ["Specialization already exists for this teacher."]})

        obj = TeacherSpecialization.objects.create(
            user_id=user_id,
            teacher_level_id=teacher_level_id,
        )

        obj.subjects.set(subject_ids or [])

        user.status = UserStatus.ACTIVE if hasattr(UserStatus, "ACTIVE") else "active"
        user.is_active = True
        user.save(update_fields=["status", "is_active"])

        return obj

    @transaction.atomic
    def update(self, instance: TeacherSpecialization, validated_data):
        # keep your existing behavior (update specialization only)
        if "user" in validated_data and validated_data["user"] != instance.user_id:
            raise serializers.ValidationError({"user": ["Changing user is not allowed."]})

        if "teacher_level" in validated_data:
            instance.teacher_level_id = validated_data.get("teacher_level", None)

        instance.save()

        if "subjects" in validated_data:
            instance.subjects.set(validated_data.get("subjects", []))

        return instance