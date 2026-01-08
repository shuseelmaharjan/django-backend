from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from drf_spectacular.utils import extend_schema, OpenApiExample

from accounts.permissions import IsSchoolAdmin
from assessments.models import StudentTestAttempt, StudentAnswer
from assessments.serializers_attempts import (
    StudentTestAttemptSerializer,
    StartAttemptSerializer,
    AnswerUpsertSerializer,
    SubmitAttemptSerializer,
    EvaluateAttemptSerializer,
)


@extend_schema(tags=["15. Attempts & Evaluation"])
class AttemptViewSet(viewsets.ModelViewSet):
    """
    Admin-only for now.
    Later:
      - Student can start/answer/submit for own attempts
      - Teacher can evaluate for assigned classes/sections
    """
    queryset = StudentTestAttempt.objects.select_related("test", "student", "student__user").all().order_by("-started_at")
    serializer_class = StudentTestAttemptSerializer
    permission_classes = [IsSchoolAdmin]
    lookup_field = "id"

    def get_queryset(self):
        qs = super().get_queryset()
        school_id = getattr(self.request, "school_id", None)
        if school_id:
            qs = qs.filter(test__school_id=school_id)

        student = self.request.query_params.get("student")
        test = self.request.query_params.get("test")
        status_ = self.request.query_params.get("status")
        if student:
            qs = qs.filter(student_id=student)
        if test:
            qs = qs.filter(test_id=test)
        if status_:
            qs = qs.filter(status=status_)
        return qs

    @extend_schema(
        description="Start an attempt for a student (checks availability window and attempt_limit).",
        request=StartAttemptSerializer,
        examples=[OpenApiExample("Start", value={"test_id": "UUID", "student_id": "UUID"})],
    )
    @action(detail=False, methods=["post"])
    def start(self, request):
        ser = StartAttemptSerializer(data=request.data, context={"request": request})
        ser.is_valid(raise_exception=True)
        att = ser.save()
        return Response(StudentTestAttemptSerializer(att).data, status=status.HTTP_201_CREATED)

    @extend_schema(
        description="Upsert an answer for an attempt+question (MCQ/TF needs selected_choice_id).",
        request=AnswerUpsertSerializer,
        examples=[OpenApiExample("Answer MCQ", value={
            "attempt_id": "UUID", "question_id": "UUID", "selected_choice_id": "UUID"
        })],
    )
    @action(detail=False, methods=["post"])
    def answer(self, request):
        ser = AnswerUpsertSerializer(data=request.data, context={"request": request})
        ser.is_valid(raise_exception=True)
        ans = ser.save()
        return Response({"detail": "Saved", "answer_id": str(ans.id)}, status=status.HTTP_200_OK)

    @extend_schema(
        description="Submit an attempt (locks further answers).",
        request=SubmitAttemptSerializer,
        examples=[OpenApiExample("Submit", value={"attempt_id": "UUID"})],
    )
    @action(detail=False, methods=["post"])
    def submit(self, request):
        ser = SubmitAttemptSerializer(data=request.data, context={"request": request})
        ser.is_valid(raise_exception=True)
        att = ser.save()
        return Response({"detail": "Submitted", "submitted_at": att.submitted_at}, status=status.HTTP_200_OK)

    @extend_schema(
        description="Evaluate attempt. Auto-evaluates MCQ/TF, manual scores for SHORT/LONG.",
        request=EvaluateAttemptSerializer,
        examples=[OpenApiExample("Evaluate", value={
            "attempt_id": "UUID",
            "manual": [{"question_id": "UUID", "marks_awarded": "2.00"}]
        })],
    )
    @action(detail=False, methods=["post"])
    def evaluate(self, request):
        ser = EvaluateAttemptSerializer(data=request.data, context={"request": request})
        ser.is_valid(raise_exception=True)
        att = ser.save()
        return Response({"detail": "Evaluated", "score": str(att.score)}, status=status.HTTP_200_OK)
