from django.db import transaction
from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from drf_spectacular.utils import extend_schema, OpenApiExample

from accounts.permissions import IsSchoolAdmin
from common.viewsets import SchoolScopedModelViewSet
from assessments.models import OnlineTest, TestQuestion
from assessments.serializers_tests import (
    OnlineTestSerializer,
    TestQuestionSerializer,
    AddQuestionToTestSerializer,
    ReorderQuestionsSerializer,
    recalc_test_total_marks,
)


@extend_schema(tags=["14. Online Tests"])
class OnlineTestViewSet(SchoolScopedModelViewSet):
    queryset = OnlineTest.objects.select_related("academic_year", "academic_class", "section", "subject").all().order_by("-created_at")
    serializer_class = OnlineTestSerializer
    permission_classes = [IsSchoolAdmin]
    lookup_field = "id"
    school_field = "school_id"

    def get_serializer_context(self):
        ctx = super().get_serializer_context()
        ctx["request"] = self.request
        return ctx

    def get_queryset(self):
        qs = super().get_queryset()
        ay = self.request.query_params.get("academic_year")
        cls = self.request.query_params.get("academic_class")
        sec = self.request.query_params.get("section")
        published = self.request.query_params.get("published")

        if ay:
            qs = qs.filter(academic_year_id=ay)
        if cls:
            qs = qs.filter(academic_class_id=cls)
        if sec:
            qs = qs.filter(section_id=sec)
        if published in ("true", "false"):
            qs = qs.filter(is_published=(published == "true"))
        return qs

    @action(detail=True, methods=["post"])
    def publish(self, request, id=None):
        test = self.get_object()
        if test.is_published:
            return Response({"detail": "Already published."}, status=status.HTTP_400_BAD_REQUEST)

        if test.start_at >= test.end_at:
            return Response({"detail": "Invalid time window."}, status=status.HTTP_400_BAD_REQUEST)

        if test.test_questions.count() == 0:
            return Response({"detail": "Add at least 1 question before publishing."}, status=status.HTTP_400_BAD_REQUEST)

        recalc_test_total_marks(test)
        test.is_published = True
        test.save(update_fields=["is_published"])
        return Response({"detail": "Published", "total_marks": str(test.total_marks)}, status=status.HTTP_200_OK)

    @action(detail=True, methods=["post"])
    def unpublish(self, request, id=None):
        test = self.get_object()
        if not test.is_published:
            return Response({"detail": "Not published."}, status=status.HTTP_400_BAD_REQUEST)
        test.is_published = False
        test.save(update_fields=["is_published"])
        return Response({"detail": "Unpublished"}, status=status.HTTP_200_OK)

    @extend_schema(
        description="Add a question to a test (upserts if already exists).",
        request=AddQuestionToTestSerializer,
        examples=[OpenApiExample("Add", value={"test_id": "UUID", "question_id": "UUID", "order": 1})],
    )
    @action(detail=False, methods=["post"])
    def add_question(self, request):
        ser = AddQuestionToTestSerializer(data=request.data, context={"request": request})
        ser.is_valid(raise_exception=True)
        tq = ser.save()
        recalc_test_total_marks(tq.test)
        return Response(TestQuestionSerializer(tq).data, status=status.HTTP_200_OK)

    @action(detail=False, methods=["post"])
    def remove_question(self, request):
        """
        Body: { "test_id": "...", "test_question_id": "..." } OR { "test_id": "...", "question_id": "..." }
        """
        school_id = request.school_id
        test_id = (request.data or {}).get("test_id")
        tq_id = (request.data or {}).get("test_question_id")
        q_id = (request.data or {}).get("question_id")

        test = OnlineTest.objects.filter(id=test_id, school_id=school_id).first()
        if not test:
            return Response({"detail": "Test not found."}, status=status.HTTP_404_NOT_FOUND)
        if test.is_published:
            return Response({"detail": "Cannot modify after publish. Unpublish first."}, status=status.HTTP_400_BAD_REQUEST)

        qs = TestQuestion.objects.filter(test=test)
        if tq_id:
            qs = qs.filter(id=tq_id)
        elif q_id:
            qs = qs.filter(question_id=q_id)
        else:
            return Response({"detail": "test_question_id or question_id required."}, status=status.HTTP_400_BAD_REQUEST)

        deleted, _ = qs.delete()
        recalc_test_total_marks(test)
        return Response({"detail": f"Removed {deleted} item(s)."}, status=status.HTTP_200_OK)

    @extend_schema(
        description="Reorder questions in a test.",
        request=ReorderQuestionsSerializer,
        examples=[OpenApiExample("Reorder", value={
            "test_id": "UUID",
            "items": [{"test_question_id": "UUID", "order": 1}, {"test_question_id": "UUID2", "order": 2}]
        })],
    )
    @action(detail=False, methods=["post"])
    def reorder_questions(self, request):
        ser = ReorderQuestionsSerializer(data=request.data, context={"request": request})
        ser.is_valid(raise_exception=True)
        test = ser.save()
        return Response({"detail": "Reordered"}, status=status.HTTP_200_OK)
