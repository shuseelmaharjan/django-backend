from drf_spectacular.utils import extend_schema, extend_schema_view
from rest_framework import mixins, status, viewsets, filters
from rest_framework.decorators import action
from rest_framework.response import Response

from common.permissions import IsPlatformSuperAdmin, IsAuthenticatedAndActive, IsTeacher

from exams.models import Exam, ExamSet
from exams.serializers import (
    ExamCreateSerializer, ExamUpdateSerializer, ExamReadSerializer,
    ExamReorderSerializer, ExamToggleActiveSerializer,
    ExamSetCreateSerializer, ExamSetUpdateSerializer, ExamSetReadSerializer,
    ExamSetReorderSerializer, ExamSetStatusToggleSerializer,
)
from exams.services import ExamService, ExamSetService
from exams.permissions import IsSubjectTeacher


# =========================
# Admin: Exam
# =========================

@extend_schema_view(
    list=extend_schema(tags=["Exam"]),
    create=extend_schema(tags=["Exam"], request=ExamCreateSerializer),
    retrieve=extend_schema(tags=["Exam"]),
    update=extend_schema(tags=["Exam"], request=ExamUpdateSerializer),
    partial_update=extend_schema(tags=["Exam"], request=ExamUpdateSerializer),
    destroy=extend_schema(tags=["Exam"]),
    reorder=extend_schema(tags=["Exam"], request=ExamReorderSerializer),
)
class ExamViewSet(
    mixins.CreateModelMixin,
    mixins.ListModelMixin,
    mixins.RetrieveModelMixin,
    mixins.UpdateModelMixin,
    mixins.DestroyModelMixin,
    viewsets.GenericViewSet,
):
    lookup_field = "pk"
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]

    search_fields = ["title", "category"]
    ordering_fields = ["sort_order", "created_at", "updated_at", "exam_year", "category", "is_active"]
    ordering = ["sort_order", "-created_at"]

    def get_permissions(self):
        if self.action in ("list", "retrieve"):
            return [IsAuthenticatedAndActive()]
        return [IsPlatformSuperAdmin()]

    def get_queryset(self):
        qs = Exam.objects.select_related("batch").all()

        category_q = (self.request.query_params.get("category") or "").strip()
        if category_q:
            qs = qs.filter(category=category_q)

        year_q = (self.request.query_params.get("exam_year") or "").strip()
        if year_q.isdigit():
            qs = qs.filter(exam_year=int(year_q))

        batch_q = (self.request.query_params.get("batch") or "").strip()
        if batch_q:
            qs = qs.filter(batch_id=batch_q)

        active_q = (self.request.query_params.get("is_active") or "").strip().lower()
        if active_q in ("1", "true", "yes"):
            qs = qs.filter(is_active=True)
        elif active_q in ("0", "false", "no"):
            qs = qs.filter(is_active=False)

        return qs

    def get_serializer_class(self):
        if self.action == "create":
            return ExamCreateSerializer
        if self.action in ("update", "partial_update"):
            return ExamUpdateSerializer
        return ExamReadSerializer

    def create(self, request, *args, **kwargs):
        serialier = ExamCreateSerializer(data=request.data, context={"request": request})
        serialier.is_valid(raise_exception=True)
        obj = ExamService.create_exam(serialier.validated_data)
        return Response(
            {"message": "Exam created.", "data": ExamReadSerializer(obj).data},
            status=status.HTTP_201_CREATED,
        )

    def update(self, request, *args, **kwargs):
        obj = self.get_object()
        serialier = ExamUpdateSerializer(instance=obj, data=request.data, partial=False, context={"request": request})
        serialier.is_valid(raise_exception=True)
        obj = ExamService.update_exam(obj, serialier.validated_data)
        return Response({"message": "Exam updated.", "data": ExamReadSerializer(obj).data})

    def partial_update(self, request, *args, **kwargs):
        obj = self.get_object()
        serialier = ExamUpdateSerializer(instance=obj, data=request.data, partial=True, context={"request": request})
        serialier.is_valid(raise_exception=True)
        obj = ExamService.update_exam(obj, serialier.validated_data)
        return Response({"message": "Exam updated.", "data": ExamReadSerializer(obj).data})

    def destroy(self, request, *args, **kwargs):
        obj = self.get_object()
        ExamService.soft_delete_exam(obj)
        return Response({"message": "Exam deactivated."}, status=status.HTTP_204_NO_CONTENT)

    @extend_schema(tags=["Exam"], request=ExamReorderSerializer)
    @action(detail=False, methods=["post"], url_path="reorder")
    def reorder(self, request):
        serialier = ExamReorderSerializer(data=request.data, context={"request": request})
        serialier.is_valid(raise_exception=True)
        ExamService.reorder(serialier.validated_data["items"])
        return Response({"message": "Exams reordered."}, status=status.HTTP_200_OK)

    @extend_schema(tags=["Exam"], request=ExamToggleActiveSerializer, responses=ExamReadSerializer)
    @action(detail=True, methods=["post"], url_path="toggle-active")
    def toggle_active(self, request, pk=None):
        obj = self.get_object()
        serialier = ExamToggleActiveSerializer(data=request.data, context={"request": request})
        serialier.is_valid(raise_exception=True)
        obj = ExamService.set_active(obj, serialier.validated_data["is_active"])
        return Response({"message": "Exam active status updated.", "data": ExamReadSerializer(obj).data},
                        status=status.HTTP_200_OK)


# =========================
# Teacher: ExamSet (subject assigned teacher)
# =========================

@extend_schema_view(
    list=extend_schema(tags=["ExamSet"]),
    create=extend_schema(tags=["ExamSet"], request=ExamSetCreateSerializer),
    retrieve=extend_schema(tags=["ExamSet"]),
    update=extend_schema(tags=["ExamSet"], request=ExamSetUpdateSerializer),
    partial_update=extend_schema(tags=["ExamSet"], request=ExamSetUpdateSerializer),
    destroy=extend_schema(tags=["ExamSet"]),
    reorder=extend_schema(tags=["ExamSet"], request=ExamSetReorderSerializer),
)
class ExamSetViewSet(
    mixins.CreateModelMixin,
    mixins.ListModelMixin,
    mixins.RetrieveModelMixin,
    mixins.UpdateModelMixin,
    mixins.DestroyModelMixin,
    viewsets.GenericViewSet,
):
    lookup_field = "pk"
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]

    search_fields = ["title", "instructions"]
    ordering_fields = ["sort_order", "created_at", "updated_at", "status"]
    ordering = ["sort_order", "created_at"]

    def get_permissions(self):
        if self.action in ("list", "retrieve"):
            return [IsAuthenticatedAndActive()]
        if self.action in ("update", "partial_update"):
            return [IsAuthenticatedAndActive(), IsSubjectTeacher()]
        return [IsAuthenticatedAndActive(), IsTeacher()]

    def get_queryset(self):
        qs = (
            ExamSet.objects
            .select_related("exam", "academic_class", "subject", "set_by")
            .prefetch_related(
                "sections",
                "sections__questions",
                "sections__questions__answer_options",
            )
            .all()
        )

        # basic filters
        exam_q = (self.request.query_params.get("exam") or "").strip()
        if exam_q:
            qs = qs.filter(exam_id=exam_q)

        subject_q = (self.request.query_params.get("subject") or "").strip()
        if subject_q:
            qs = qs.filter(subject_id=subject_q)

        class_q = (self.request.query_params.get("academic_class") or "").strip()
        if class_q:
            qs = qs.filter(academic_class_id=class_q)

        status_q = (self.request.query_params.get("status") or "").strip()
        if status_q:
            qs = qs.filter(status=status_q)

        user = self.request.user
        if getattr(user, "is_staff", False):
            return qs

        # Teacher: limit to subjects they are assigned in
        if getattr(user, "is_teacher", False):
            subject_ids = TeacherSpecialization.objects.filter(user=user).values_list("subjects__id", flat=True)
            qs = qs.filter(subject_id__in=subject_ids)

            # default: only mine (if you want). Keep your previous param:
            only_mine = (self.request.query_params.get("only_mine") or "").strip().lower() in ("1", "true", "yes")
            if only_mine or True:  # set True to always restrict to own examsets by default
                qs = qs.filter(set_by=user)
        
        return qs

    def get_serializer_class(self):
        if self.action == "create":
            return ExamSetCreateSerializer
        if self.action in ("update", "partial_update"):
            return ExamSetUpdateSerializer
        return ExamSetReadSerializer

    def create(self, request, *args, **kwargs):
        serialier = ExamSetCreateSerializer(data=request.data, context={"request": request})
        serialier.is_valid(raise_exception=True)

        exam_set = ExamSetService.create_examset(serialier.validated_data, teacher=request.user)

        return Response(
            {"message": "ExamSet created.", "data": ExamSetReadSerializer(exam_set).data},
            status=status.HTTP_201_CREATED,
        )

    def update(self, request, *args, **kwargs):
        obj = self.get_object()
        self.check_object_permissions(request, obj)

        serialier = ExamSetUpdateSerializer(instance=obj, data=request.data, partial=False, context={"request": request})
        serialier.is_valid(raise_exception=True)
        obj = ExamSetService.update_examset(obj, serialier.validated_data, teacher=request.user)

        return Response({"message": "ExamSet updated.", "data": ExamSetReadSerializer(obj).data})

    def partial_update(self, request, *args, **kwargs):
        obj = self.get_object()
        self.check_object_permissions(request, obj)

        serialier = ExamSetUpdateSerializer(instance=obj, data=request.data, partial=True, context={"request": request})
        serialier.is_valid(raise_exception=True)
        obj = ExamSetService.update_examset(obj, serialier.validated_data, teacher=request.user)

        return Response({"message": "ExamSet updated.", "data": ExamSetReadSerializer(obj).data})

    def destroy(self, request, *args, **kwargs):
        obj = self.get_object()
        self.check_object_permissions(request, obj)
        ExamSetService.delete_examset(obj, teacher=request.user)
        return Response({"message": "ExamSet deleted."}, status=status.HTTP_204_NO_CONTENT)

    @extend_schema(tags=["ExamSet"], request=ExamSetReorderSerializer)
    @action(detail=False, methods=["post"], url_path="reorder")
    def reorder(self, request):
        serialier = ExamSetReorderSerializer(data=request.data, context={"request": request})
        serialier.is_valid(raise_exception=True)
        ExamSetService.reorder(serialier.validated_data["items"])
        return Response({"message": "ExamSets reordered."}, status=status.HTTP_200_OK)

    @extend_schema(tags=["ExamSet"], request=ExamSetStatusToggleSerializer, responses=ExamSetReadSerializer)
    @action(detail=True, methods=["post"], url_path="toggle-status")
    def toggle_status(self, request, pk=None):
        obj = self.get_object()
        self.check_object_permissions(request, obj)

        serialier = ExamSetStatusToggleSerializer(data=request.data, context={"request": request})
        serialier.is_valid(raise_exception=True)
        obj = ExamSetService.set_status(obj, serialier.validated_data["status"])
        return Response(
            {"message": "ExamSet status updated.", "data": ExamSetReadSerializer(obj).data},
            status=status.HTTP_200_OK,
        )
