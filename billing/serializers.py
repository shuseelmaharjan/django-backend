from __future__ import annotations

from typing import Any, Dict, Optional
import uuid

from django.core.exceptions import ValidationError as DjangoValidationError
from rest_framework import serializers

from utils.get_school_id_by_token import get_school_for_user
from .models import Billing
from django.contrib.auth import get_user_model
User = get_user_model()

class BillingCreateSerializer(serializers.Serializer):
    student = serializers.PrimaryKeyRelatedField(queryset=User.objects.all())
    amount = serializers.DecimalField(max_digits=10, decimal_places=2)
    inwords = serializers.CharField(max_length=255)
    description = serializers.CharField(allow_blank=True, required=False, default="")
    status = serializers.ChoiceField(
        choices=[("pending", "Pending"), ("paid", "Paid"), ("overdue", "Overdue")],
        required=False,
        default="pending",
    )
    payment_method = serializers.ChoiceField(
        choices=[
            ("cash", "Cash"),
            ("esewa", "Esewa"),
            ("khalti", "Khalti"),
            ("bank_transfer", "Bank Transfer"),
        ],
        required=False,
        allow_null=True,
    )
    receipt_number = serializers.CharField(max_length=50, required=False, allow_blank=True)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Import here to avoid circular import issues if any
        from accounts.models import User  # adjust if your user model path differs
        self.fields["student"].queryset = User.objects.all()

    def validate(self, attrs: Dict[str, Any]) -> Dict[str, Any]:
        request = self.context["request"]
        school = get_school_for_user(request.user)

        # basic cleanup
        attrs["inwords"] = (attrs.get("inwords") or "").strip()
        if not attrs["inwords"]:
            raise serializers.ValidationError({"inwords": ["This field may not be blank."]})

        # ensure student belongs to same school (assuming User has school_id)
        student = attrs["student"]
        if hasattr(student, "school_id") and student.school_id != school.id:
            raise serializers.ValidationError({"student": ["Student does not belong to your school."]})

        status = attrs.get("status", "pending")
        payment_method = attrs.get("payment_method")

        if status == "paid" and not payment_method:
            raise serializers.ValidationError({"payment_method": ["Payment method is required when status is paid."]})

        return attrs

    def create(self, validated_data: Dict[str, Any]) -> Billing:
        request = self.context["request"]

        receipt_number = (validated_data.get("receipt_number") or "").strip()
        if not receipt_number:
            # simple unique-ish receipt
            receipt_number = f"RCPT-{uuid.uuid4().hex[:10].upper()}"

        obj = Billing(
            student=validated_data["student"],
            amount=validated_data["amount"],
            inwords=validated_data["inwords"],
            description=validated_data.get("description", ""),
            status=validated_data.get("status", "pending"),
            payment_method=validated_data.get("payment_method"),
            receipt_number=receipt_number,
        )

        # if paid, set received_by to current user (cashier/admin)
        if obj.status == "paid":
            obj.received_by = request.user

        try:
            obj.save()
        except DjangoValidationError as e:
            if hasattr(e, "message_dict"):
                raise serializers.ValidationError(e.message_dict)
            raise serializers.ValidationError({"detail": e.messages})

        return obj


class BillingUpdateSerializer(serializers.Serializer):
    amount = serializers.DecimalField(max_digits=10, decimal_places=2, required=False)
    inwords = serializers.CharField(max_length=255, required=False)
    description = serializers.CharField(allow_blank=True, required=False)
    status = serializers.ChoiceField(
        choices=[("pending", "Pending"), ("paid", "Paid"), ("overdue", "Overdue")],
        required=False,
    )
    payment_method = serializers.ChoiceField(
        choices=[
            ("cash", "Cash"),
            ("esewa", "Esewa"),
            ("khalti", "Khalti"),
            ("bank_transfer", "Bank Transfer"),
        ],
        required=False,
        allow_null=True,
    )

    def validate(self, attrs: Dict[str, Any]) -> Dict[str, Any]:
        if "inwords" in attrs:
            attrs["inwords"] = (attrs["inwords"] or "").strip()
            if not attrs["inwords"]:
                raise serializers.ValidationError({"inwords": ["This field may not be blank."]})

        status = attrs.get("status")
        payment_method = attrs.get("payment_method", None)

        # If client is setting status to paid, ensure payment_method exists either now or already on instance
        if status == "paid":
            instance: Billing = self.context["instance"]
            effective_method = payment_method if "payment_method" in attrs else instance.payment_method
            if not effective_method:
                raise serializers.ValidationError({"payment_method": ["Payment method is required when status is paid."]})

        return attrs

    def update(self, instance: Billing, validated_data: Dict[str, Any]) -> Billing:
        request = self.context["request"]

        for f in ["amount", "inwords", "description", "status", "payment_method"]:
            if f in validated_data:
                setattr(instance, f, validated_data[f])

        # if status becomes paid, set received_by
        if "status" in validated_data and instance.status == "paid" and instance.received_by_id is None:
            instance.received_by = request.user

        # if status becomes pending/overdue, you may want to clear payment info
        if "status" in validated_data and instance.status in ("pending", "overdue"):
            instance.payment_method = None
            instance.received_by = None

        try:
            instance.save()
        except DjangoValidationError as e:
            if hasattr(e, "message_dict"):
                raise serializers.ValidationError(e.message_dict)
            raise serializers.ValidationError({"detail": e.messages})

        return instance


class BillingReadSerializer(serializers.ModelSerializer):
    student_detail = serializers.SerializerMethodField()
    received_by_detail = serializers.SerializerMethodField()

    class Meta:
        model = Billing
        fields = [
            "id",
            "student",
            "student_detail",
            "amount",
            "inwords",
            "description",
            "status",
            "payment_method",
            "receipt_number",
            "received_by",
            "received_by_detail",
            "created_at",
        ]

    def get_student_detail(self, obj: Billing) -> Dict[str, Any]:
        u = obj.student
        return {"id": u.id, "name": getattr(u, "full_name", str(u)), "username": getattr(u, "username", None)}

    def get_received_by_detail(self, obj: Billing) -> Optional[Dict[str, Any]]:
        if not obj.received_by:
            return None
        u = obj.received_by
        return {"id": u.id, "name": getattr(u, "full_name", str(u)), "username": getattr(u, "username", None)}


class BillingUndoSerializer(serializers.Serializer):
    """
    mode:
      - unpay: revert paid -> pending (clears payment_method + received_by)
      - void: delete the record (hard delete)  [no soft-delete field in model]
    """
    mode = serializers.ChoiceField(choices=[("unpay", "Unpay"), ("void", "Void")])
    reason = serializers.CharField(required=False, allow_blank=True, default="")
