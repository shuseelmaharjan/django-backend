from __future__ import annotations

from drf_spectacular.utils import extend_schema, extend_schema_view
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView

from common.permissions import IsAuthenticatedAndActive, IsSchoolAdmin
from academics.serializers_enroll import StudentEnrollAndSetupFeesSerializer


@extend_schema_view(
    post=extend_schema(
        tags=["Student Enrollment"],
        request=StudentEnrollAndSetupFeesSerializer,
        responses={201: dict},
    )
)
class StudentEnrollAndSetupFeesAPI(APIView):
    """
    POST:
    - marks student as enrolled (StudentEnrollments)
    - activates student user
    - creates FeeInclude rows + FeeIncludeAudit
    - upserts StudentFeeWallet for batch+class
    """
    permission_classes = [IsAuthenticatedAndActive, IsSchoolAdmin]

    def post(self, request):
        s = StudentEnrollAndSetupFeesSerializer(data=request.data, context={"request": request})
        s.is_valid(raise_exception=True)

        result = s.save()
        enrollment = result["enrollment"]
        wallet = result["wallet"]
        created_includes = result["fee_includes_created"]

        return Response(
            {
                "message": "Student enrolled and fee setup completed.",
                "data": {
                    "enrollment": {
                        "id": str(enrollment.id),
                        "student": str(enrollment.student_id),
                        "batch": enrollment.batch_id,
                        "academic_class": str(enrollment.academic_class_id),
                        "section": str(enrollment.section_id) if enrollment.section_id else None,
                        "status": enrollment.status,
                        "enrolled_at": enrollment.enrolled_at,
                    },
                    "wallet": {
                        "id": str(wallet.id),
                        "student": str(wallet.student_id),
                        "batch": wallet.batch_id,
                        "academic_class": str(wallet.academic_class_id),
                        "total_payable": str(wallet.total_payable),
                        "total_paid": str(wallet.total_paid),
                        "total_discount": str(wallet.total_discount),
                        "total_scholarship": str(wallet.total_scholarship),
                        "total_due": str(wallet.total_due),
                        "updated_at": wallet.updated_at,
                    },
                    "fee_includes_created_count": len(created_includes),
                    "fee_includes_created": [str(x.id) for x in created_includes],
                },
            },
            status=status.HTTP_201_CREATED,
        )
