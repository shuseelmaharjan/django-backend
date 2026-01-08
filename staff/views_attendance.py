from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from drf_spectacular.utils import extend_schema, OpenApiExample

from accounts.permissions import IsSchoolAdmin
from staff.models import StaffAttendance
from staff.serializers_attendance import (
    StaffAttendanceSerializer,
    MarkAttendanceRequestSerializer,
)


@extend_schema(tags=["10. Staff Attendance"])
class StaffAttendanceViewSet(viewsets.ModelViewSet):
    """
    Admin-only attendance marking/listing (for now).
    Later: allow staff self read, and teacher/HR scoped.
    """
    queryset = StaffAttendance.objects.select_related("staff", "staff__user", "marked_by").all()
    serializer_class = StaffAttendanceSerializer
    permission_classes = [IsSchoolAdmin]
    lookup_field = "id"

    def get_queryset(self):
        qs = super().get_queryset()
        school_id = getattr(self.request, "school_id", None)
        if school_id:
            qs = qs.filter(staff__school_id=school_id)

        date = self.request.query_params.get("date")
        staff_id = self.request.query_params.get("staff")
        status_ = self.request.query_params.get("status")

        if date:
            qs = qs.filter(date=date)
        if staff_id:
            qs = qs.filter(staff_id=staff_id)
        if status_:
            qs = qs.filter(status=status_)
        return qs.order_by("-date", "staff__user__email")

    @extend_schema(
        description="Create or update attendance for a staff+date (idempotent).",
        request=MarkAttendanceRequestSerializer,
        examples=[
            OpenApiExample(
                "Mark present",
                value={
                    "staff_id": "UUID",
                    "date": "2026-01-08",
                    "status": "present",
                    "check_in": "2026-01-08T10:00:00+05:45",
                    "check_out": "2026-01-08T17:00:00+05:45",
                    "remarks": ""
                },
            )
        ],
    )
    @action(detail=False, methods=["post"])
    def mark(self, request):
        ser = MarkAttendanceRequestSerializer(data=request.data, context={"request": request})
        ser.is_valid(raise_exception=True)
        att = ser.save()
        return Response(StaffAttendanceSerializer(att).data, status=status.HTTP_200_OK)
