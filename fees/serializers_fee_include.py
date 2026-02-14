from rest_framework import serializers
from django.db import transaction
from fees.models import FeeInclude, FeeStatus, FeeIncludeAudit, FeeIncludeAuditAction
from academics.models import StudentEnrollments, EnrollmentStatus
from common.constants import UserRole

class FeeIncludeSerializer(serializers.ModelSerializer):
    class Meta:
        model = FeeInclude
        fields = [
            "id",
            "fees",
            "user",
            "batch",
            "classroom",
            "status",
            "created_at",
        ]
        read_only_fields = ["id", "created_at"]

    def validate(self, attrs):
        request = self.context["request"]

        # ✅ only student users can create/update
        if request.user.role != UserRole.STUDENT:
            raise serializers.ValidationError({"detail": "Only students are allowed to manage FeeInclude."})

        # ✅ students can only operate on themselves
        target_user = attrs.get("user") or (self.instance.user if self.instance else None)
        if target_user and target_user.id != request.user.id:
            raise serializers.ValidationError({"user": "You can only manage your own fees."})

        # ✅ must be enrolled (or handle your draft->enrolled logic elsewhere)
        batch = attrs.get("batch") or (self.instance.batch if self.instance else None)
        classroom = attrs.get("classroom") or (self.instance.classroom if self.instance else None)

        if batch and classroom:
            ok = StudentEnrollments.objects.filter(
                student=request.user,
                batch=batch,
                academic_class=classroom,
                status=EnrollmentStatus.ENROLLED,
            ).exists()
            if not ok:
                raise serializers.ValidationError({"detail": "You must be enrolled in this batch/class."})

        return attrs

    @transaction.atomic
    def create(self, validated_data):
        request = self.context["request"]
        obj = super().create(validated_data)

        FeeIncludeAudit.objects.create(
            fee_include=obj,
            actor=request.user,
            action=FeeIncludeAuditAction.CREATE,
            prev_status="",
            new_status=obj.status,
            prev_batch_id=None,
            new_batch_id=obj.batch_id,
            prev_class_id=None,
            new_class_id=obj.classroom_id,
        )
        return obj

    @transaction.atomic
    def update(self, instance, validated_data):
        request = self.context["request"]

        prev_status = instance.status
        prev_batch_id = instance.batch_id
        prev_class_id = instance.classroom_id

        obj = super().update(instance, validated_data)

        FeeIncludeAudit.objects.create(
            fee_include=obj,
            actor=request.user,
            action=FeeIncludeAuditAction.UPDATE,
            prev_status=prev_status,
            new_status=obj.status,
            prev_batch_id=prev_batch_id,
            new_batch_id=obj.batch_id,
            prev_class_id=prev_class_id,
            new_class_id=obj.classroom_id,
        )
        return obj
