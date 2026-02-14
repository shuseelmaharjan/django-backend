from rest_framework import mixins, status, viewsets, filters
from rest_framework.response import Response
from rest_framework.decorators import action
from django.db import transaction

from common.permissions import IsAuthenticatedAndActive
from fees.models import FeeInclude, FeeStatus, FeeIncludeAudit, FeeIncludeAuditAction
from fees.serializers_fee_include import FeeIncludeSerializer

class FeeIncludeViewSet(
    mixins.CreateModelMixin,
    mixins.ListModelMixin,
    mixins.RetrieveModelMixin,
    mixins.UpdateModelMixin,
    viewsets.GenericViewSet,
):
    serializer_class = FeeIncludeSerializer
    permission_classes = [IsAuthenticatedAndActive]

    filter_backends = [filters.OrderingFilter]
    ordering_fields = ["created_at", "status"]
    ordering = ["-created_at"]

    def get_queryset(self):
        # student sees only their own
        return FeeInclude.objects.filter(user=self.request.user).select_related("fees", "batch", "classroom")

    def create(self, request, *args, **kwargs):
        s = self.get_serializer(data=request.data, context={"request": request})
        s.is_valid(raise_exception=True)
        obj = s.save()
        return Response({"message": "FeeInclude created.", "data": self.get_serializer(obj).data}, status=201)

    def update(self, request, *args, **kwargs):
        obj = self.get_object()
        s = self.get_serializer(instance=obj, data=request.data, partial=False, context={"request": request})
        s.is_valid(raise_exception=True)
        obj = s.save()
        return Response({"message": "FeeInclude updated.", "data": self.get_serializer(obj).data})

    def partial_update(self, request, *args, **kwargs):
        obj = self.get_object()
        s = self.get_serializer(instance=obj, data=request.data, partial=True, context={"request": request})
        s.is_valid(raise_exception=True)
        obj = s.save()
        return Response({"message": "FeeInclude updated.", "data": self.get_serializer(obj).data})

    @transaction.atomic
    def destroy(self, request, *args, **kwargs):
        obj = self.get_object()
        prev = obj.status
        obj.status = FeeStatus.deleted
        obj.save(update_fields=["status"])

        FeeIncludeAudit.objects.create(
            fee_include=obj,
            actor=request.user,
            action=FeeIncludeAuditAction.DELETE,
            prev_status=prev,
            new_status=obj.status,
            prev_batch_id=obj.batch_id,
            new_batch_id=obj.batch_id,
            prev_class_id=obj.classroom_id,
            new_class_id=obj.classroom_id,
        )

        return Response({"message": "FeeInclude deleted."}, status=status.HTTP_200_OK)

    @action(detail=True, methods=["post"], url_path="undo")
    @transaction.atomic
    def undo(self, request, pk=None):
        obj = self.get_object()

        last = obj.audits.order_by("-created_at").first()
        if not last:
            return Response({"detail": "Nothing to undo."}, status=400)

        # Undo create/delete/update by reverting to prev_* fields
        # For create: you may set deleted; for delete: restore prev_status; for update: revert fields.
        if last.action == FeeIncludeAuditAction.CREATE:
            obj.status = FeeStatus.deleted
        else:
            if last.prev_status:
                obj.status = last.prev_status
            if last.prev_batch_id is not None:
                obj.batch_id = last.prev_batch_id
            if last.prev_class_id is not None:
                obj.classroom_id = last.prev_class_id

        obj.save()

        FeeIncludeAudit.objects.create(
            fee_include=obj,
            actor=request.user,
            action=FeeIncludeAuditAction.UNDO,
            prev_status=last.new_status,
            new_status=obj.status,
            prev_batch_id=last.new_batch_id,
            new_batch_id=obj.batch_id,
            prev_class_id=last.new_class_id,
            new_class_id=obj.classroom_id,
        )

        return Response({"message": "Undo successful.", "data": self.get_serializer(obj).data})
