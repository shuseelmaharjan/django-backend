from decimal import Decimal
from django.db import transaction
from django.utils import timezone
from rest_framework import serializers

from assessments.models import (
    OnlineTest, TestQuestion, StudentTestAttempt, StudentAnswer,
    AttemptStatus, QuestionType, QuestionChoice
)
from students.models import StudentProfile
from enrollment.models import StudentEnrollment


class StudentTestAttemptSerializer(serializers.ModelSerializer):
    test_title = serializers.CharField(source="test.title", read_only=True)
    student_email = serializers.EmailField(source="student.user.email", read_only=True)

    class Meta:
        model = StudentTestAttempt
        fields = [
            "id",
            "test", "test_title",
            "student", "student_email",
            "attempt_no",
            "started_at", "submitted_at",
            "status",
            "score",
        ]
        read_only_fields = ["id", "attempt_no", "started_at", "submitted_at", "status", "score"]


class StartAttemptSerializer(serializers.Serializer):
    test_id = serializers.UUIDField()
    student_id = serializers.UUIDField()

    def validate(self, attrs):
        request = self.context["request"]
        school_id = request.school_id

        test = OnlineTest.objects.filter(id=attrs["test_id"], school_id=school_id, is_published=True).first()
        if not test:
            raise serializers.ValidationError({"test_id": "Published test not found in this school."})

        now = timezone.now()
        if not (test.start_at <= now <= test.end_at):
            raise serializers.ValidationError("Test is not currently available.")

        student = StudentProfile.objects.filter(id=attrs["student_id"], school_id=school_id).first()
        if not student:
            raise serializers.ValidationError({"student_id": "Student not found in this school."})

        # must be enrolled in that class/section/year
        enr = StudentEnrollment.objects.filter(
            school_id=school_id,
            student=student,
            academic_year=test.academic_year,
            academic_class=test.academic_class,
            is_active=True,
        ).first()
        if not enr:
            raise serializers.ValidationError("Student is not enrolled in the target class/year.")

        if test.section_id and enr.section_id != test.section_id:
            raise serializers.ValidationError("Student not in the target section.")

        attrs["_test"] = test
        attrs["_student"] = student
        return attrs

    def create(self, validated_data):
        test = validated_data["_test"]
        student = validated_data["_student"]

        # attempt limit
        used = StudentTestAttempt.objects.filter(test=test, student=student).count()
        if used >= test.attempt_limit:
            raise serializers.ValidationError("Attempt limit reached.")

        attempt_no = used + 1
        att = StudentTestAttempt.objects.create(
            test=test,
            student=student,
            attempt_no=attempt_no,
            status=AttemptStatus.IN_PROGRESS,
        )
        return att


class AnswerUpsertSerializer(serializers.Serializer):
    attempt_id = serializers.UUIDField()
    question_id = serializers.UUIDField()
    selected_choice_id = serializers.UUIDField(required=False, allow_null=True)
    answer_text = serializers.CharField(required=False, allow_blank=True, default="")

    def validate(self, attrs):
        request = self.context["request"]
        school_id = request.school_id

        att = StudentTestAttempt.objects.select_related(
            "test", "student"
        ).filter(id=attrs["attempt_id"]).first()
        if not att:
            raise serializers.ValidationError({"attempt_id": "Attempt not found."})
        if att.test.school_id != school_id or att.student.school_id != school_id:
            raise serializers.ValidationError("Attempt not in this school.")
        if att.status != AttemptStatus.IN_PROGRESS:
            raise serializers.ValidationError("Attempt is not in progress.")

        # ensure question is in the test
        tq = TestQuestion.objects.select_related("question").filter(test=att.test, question_id=attrs["question_id"]).first()
        if not tq:
            raise serializers.ValidationError({"question_id": "Question not part of this test."})

        q = tq.question
        attrs["_attempt"] = att
        attrs["_question"] = q
        attrs["_marks"] = tq.marks_override if tq.marks_override is not None else q.marks

        if q.qtype in (QuestionType.MCQ, QuestionType.TRUE_FALSE):
            cid = attrs.get("selected_choice_id")
            if not cid:
                raise serializers.ValidationError({"selected_choice_id": "Choice required for MCQ/TF."})
            choice = QuestionChoice.objects.filter(id=cid, question=q).first()
            if not choice:
                raise serializers.ValidationError({"selected_choice_id": "Invalid choice."})
            attrs["_choice"] = choice
        else:
            # for short/long, accept answer_text
            attrs["_choice"] = None

        return attrs

    def create(self, validated_data):
        att = validated_data["_attempt"]
        q = validated_data["_question"]
        choice = validated_data["_choice"]
        answer_text = validated_data.get("answer_text", "")

        obj, _ = StudentAnswer.objects.update_or_create(
            attempt=att,
            question=q,
            defaults={
                "selected_choice": choice,
                "answer_text": answer_text,
            },
        )
        return obj


class SubmitAttemptSerializer(serializers.Serializer):
    attempt_id = serializers.UUIDField()

    def validate(self, attrs):
        request = self.context["request"]
        school_id = request.school_id

        att = StudentTestAttempt.objects.select_related("test").filter(id=attrs["attempt_id"]).first()
        if not att:
            raise serializers.ValidationError({"attempt_id": "Attempt not found."})
        if att.test.school_id != school_id:
            raise serializers.ValidationError("Attempt not in this school.")
        if att.status != AttemptStatus.IN_PROGRESS:
            raise serializers.ValidationError("Only in-progress attempts can be submitted.")
        attrs["_attempt"] = att
        return attrs

    def create(self, validated_data):
        att = validated_data["_attempt"]
        att.status = AttemptStatus.SUBMITTED
        att.submitted_at = timezone.now()
        att.save(update_fields=["status", "submitted_at"])
        return att


class EvaluateAttemptSerializer(serializers.Serializer):
    """
    Auto-evaluate MCQ/TF; keep SHORT/LONG marks as given by evaluator.
    Body:
      {
        "attempt_id": "...",
        "manual": [{"question_id": "...", "marks_awarded": "2.00"}]
      }
    """
    attempt_id = serializers.UUIDField()
    manual = serializers.ListField(child=serializers.DictField(), required=False, default=list)

    def validate(self, attrs):
        request = self.context["request"]
        school_id = request.school_id

        att = StudentTestAttempt.objects.select_related("test").filter(id=attrs["attempt_id"]).first()
        if not att:
            raise serializers.ValidationError({"attempt_id": "Attempt not found."})
        if att.test.school_id != school_id:
            raise serializers.ValidationError("Attempt not in this school.")
        if att.status not in (AttemptStatus.SUBMITTED, AttemptStatus.EVALUATED):
            raise serializers.ValidationError("Attempt must be submitted before evaluation.")
        attrs["_attempt"] = att
        return attrs

    def create(self, validated_data):
        att = validated_data["_attempt"]
        test = att.test

        # map marks per question
        tq_map = {
            str(tq.question_id): (tq.marks_override if tq.marks_override is not None else tq.question.marks, tq.question.qtype)
            for tq in TestQuestion.objects.select_related("question").filter(test=test)
        }

        manual_map = {}
        for it in validated_data.get("manual") or []:
            qid = str(it.get("question_id") or "")
            if not qid:
                continue
            manual_map[qid] = Decimal(str(it.get("marks_awarded") or "0"))

        total = Decimal("0.00")

        with transaction.atomic():
            answers = list(StudentAnswer.objects.select_related("question", "selected_choice").filter(attempt=att))

            for ans in answers:
                qid = str(ans.question_id)
                if qid not in tq_map:
                    continue
                max_marks, qtype = tq_map[qid]

                if qtype in (QuestionType.MCQ, QuestionType.TRUE_FALSE):
                    correct = bool(ans.selected_choice and ans.selected_choice.is_correct)
                    ans.is_correct = correct
                    ans.marks_awarded = max_marks if correct else Decimal("0.00")
                    ans.save(update_fields=["is_correct", "marks_awarded"])
                else:
                    # manual questions
                    given = manual_map.get(qid)
                    if given is None:
                        given = Decimal(str(ans.marks_awarded or "0"))
                    if given < 0:
                        given = Decimal("0.00")
                    if given > Decimal(str(max_marks)):
                        given = Decimal(str(max_marks))
                    ans.marks_awarded = given
                    ans.save(update_fields=["marks_awarded"])

                total += Decimal(str(ans.marks_awarded or "0"))

            att.score = total
            att.status = AttemptStatus.EVALUATED
            att.save(update_fields=["score", "status"])

        return att
