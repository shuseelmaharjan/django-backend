from __future__ import annotations

import uuid
from django.db.models import Q
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.exceptions import ValidationError

from common.permissions import IsAuthenticatedAndActive
from utils.get_school_id_by_token import get_school_for_user

from batch.models import AcademicBatch
from fees.models import FeeStructure, FeeScope, FeeStatus
from fees.serializers_applicable import FeeStructureApplicableSerializer, AcademicBatchFullSerializer


class FeeStructureApplicableAPIView(APIView):
    permission_classes = [IsAuthenticatedAndActive]

    def get(self, request):
        school = get_school_for_user(request.user)

        batch_id_raw = (request.query_params.get("batch_id") or "").strip()
        class_id_raw = (request.query_params.get("class_id") or "").strip()

        if not batch_id_raw:
            raise ValidationError({"batch_id": ["batch_id is required."]})
        if not batch_id_raw.isdigit():
            raise ValidationError({"batch_id": ["batch_id must be an integer."]})
        if not class_id_raw:
            raise ValidationError({"class_id": ["class_id is required."]})

        batch_id = int(batch_id_raw)

        # protect against trailing slash + invalid uuid
        class_id_raw = class_id_raw.rstrip("/")
        try:
            class_id = uuid.UUID(class_id_raw)
        except Exception:
            raise ValidationError({"class_id": ["class_id must be a valid UUID."]})

        # ✅ Fetch requested batch (full info) and confirm same school
        batch = AcademicBatch.objects.select_related("school").filter(id=batch_id).first()
        if not batch:
            raise ValidationError({"batch_id": ["Batch not found."]})
        if batch.school_id != school.id:
            raise ValidationError({"batch_id": ["Batch does not belong to your school."]})

        qs = (
            FeeStructure.objects
            .select_related("fee_head", "school", "batch", "academic_class")
            .filter(school=school, status=FeeStatus.active)
            .filter(
                Q(scope=FeeScope.GLOBAL)
                | Q(scope=FeeScope.BATCH, batch_id=batch_id)
                | Q(scope=FeeScope.CLASS, academic_class_id=class_id)
                | Q(scope=FeeScope.BATCH_CLASS, batch_id=batch_id, academic_class_id=class_id)
            )
            .order_by("fee_head__name", "period", "scope", "amount")
        )

        return Response(
            {
                "message": "Applicable fee structures.",
                "batch": AcademicBatchFullSerializer(batch).data,   # ✅ top-level batch info
                "data": FeeStructureApplicableSerializer(qs, many=True, context={"request": request}).data,
            },
            status=status.HTTP_200_OK,
        )
