from django.utils import timezone
from rest_framework import serializers
from staff.models import StaffAttendance, StaffProfile


class StaffAttendanceSerializer(serializers.ModelSerializer):
    staff_email = serializers.EmailField(source="staff.user.email", read_only=True)
    staff_type = serializers.CharField(source="staff.staff_type", read_only=True)

    class Meta:
        model = StaffAttendance
        fields = [
            "id",
            "staff", "staff_email", "staff_type",
            "date",
            "check_in", "check_out",
            "status", "remarks",
            "marked_by",
        ]
        read_only_fields = ["id", "marked_by"]


class MarkAttendanceRequestSerializer(serializers.Serializer):
    """
    Mark attendance for one staff on one date.
    Uses uq_staff_attendance_day constraint to prevent duplicates.
    """
    staff_id = serializers.UUIDField()
    date = serializers.DateField(required=False)
    status = serializers.CharField()  # must match StaffAttendanceStatus choices
    check_in = serializers.DateTimeField(required=False, allow_null=True)
    check_out = serializers.DateTimeField(required=False, allow_null=True)
    remarks = serializers.CharField(required=False, allow_blank=True, default="")

    def validate(self, attrs):
        request = self.context["request"]
        school_id = request.school_id

        staff = StaffProfile.objects.select_related("user").filter(
            id=attrs["staff_id"],
            school_id=school_id,
        ).first()
        if not staff:
            raise serializers.ValidationError({"staff_id": "Staff not found in this school."})

        attrs["_staff"] = staff
        attrs["date"] = attrs.get("date") or timezone.localdate()
        return attrs

    def create(self, validated_data):
        request = self.context["request"]
        staff = validated_data["_staff"]

        obj, _ = StaffAttendance.objects.update_or_create(
            staff=staff,
            date=validated_data["date"],
            defaults={
                "status": validated_data["status"],
                "check_in": validated_data.get("check_in"),
                "check_out": validated_data.get("check_out"),
                "remarks": validated_data.get("remarks", ""),
                "marked_by": request.user,
            },
        )
        return obj
