from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from drf_spectacular.utils import extend_schema, OpenApiExample

from accounts.permissions import IsSchoolAdmin
from common.viewsets import SchoolScopedModelViewSet
from assessments.models import QuestionBank, Question, QuestionChoice
from assessments.serializers_core import (
    QuestionBankSerializer,
    QuestionSerializer,
    QuestionChoiceSerializer,
    QuestionChoiceBulkUpsertSerializer,
)


@extend_schema(tags=["13. Assessments Core"])
class QuestionBankViewSet(SchoolScopedModelViewSet):
    queryset = QuestionBank.objects.select_related("subject").all().order_by("-id")
    serializer_class = QuestionBankSerializer
    permission_classes = [IsSchoolAdmin]
    lookup_field = "id"
    school_field = "school_id"

    def get_queryset(self):
        qs = super().get_queryset()
        subject = self.request.query_params.get("subject")
        if subject:
            qs = qs.filter(subject_id=subject)
        return qs


@extend_schema(tags=["13. Assessments Core"])
class QuestionViewSet(viewsets.ModelViewSet):
    queryset = Question.objects.select_related("bank", "bank__subject").prefetch_related("choices").all()
    serializer_class = QuestionSerializer
    permission_classes = [IsSchoolAdmin]
    lookup_field = "id"

    def get_queryset(self):
        qs = super().get_queryset()
        school_id = getattr(self.request, "school_id", None)
        if school_id:
            qs = qs.filter(bank__school_id=school_id)

        bank = self.request.query_params.get("bank")
        qtype = self.request.query_params.get("qtype")
        if bank:
            qs = qs.filter(bank_id=bank)
        if qtype:
            qs = qs.filter(qtype=qtype)
        return qs.order_by("-id")

    def get_serializer_context(self):
        ctx = super().get_serializer_context()
        ctx["request"] = self.request
        return ctx

    @extend_schema(
        description="Bulk upsert choices for a question (MCQ/TF only).",
        request=QuestionChoiceBulkUpsertSerializer,
        examples=[OpenApiExample("Upsert", value={
            "question_id": "UUID",
            "choices": [
                {"text": "Option A", "is_correct": False},
                {"text": "Option B", "is_correct": True},
            ]
        })],
    )
    @action(detail=False, methods=["post"])
    def upsert_choices(self, request):
        ser = QuestionChoiceBulkUpsertSerializer(data=request.data, context={"request": request})
        ser.is_valid(raise_exception=True)
        q = ser.save()
        return Response(QuestionSerializer(q).data, status=status.HTTP_200_OK)


@extend_schema(tags=["13. Assessments Core"])
class QuestionChoiceViewSet(viewsets.ModelViewSet):
    queryset = QuestionChoice.objects.select_related("question", "question__bank").all()
    serializer_class = QuestionChoiceSerializer
    permission_classes = [IsSchoolAdmin]
    lookup_field = "id"

    def get_queryset(self):
        qs = super().get_queryset()
        school_id = getattr(self.request, "school_id", None)
        if school_id:
            qs = qs.filter(question__bank__school_id=school_id)
        question = self.request.query_params.get("question")
        if question:
            qs = qs.filter(question_id=question)
        return qs
