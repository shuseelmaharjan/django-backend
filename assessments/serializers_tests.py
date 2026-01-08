from decimal import Decimal
from django.db import transaction
from rest_framework import serializers
from assessments.models import OnlineTest, TestQuestion, Question, Subject
from academics.models import AcademicYear, AcademicClass, Section


class OnlineTestSerializer(serializers.ModelSerializer):
    subject_code = serializers.CharField(source="subject.code", read_only=True)
    class_name = serializers.CharField(source="academic_class.name", read_only=True)
    section_name = serializers.CharField(source="section.name", read_only=True)
    test_questions_count = serializers.IntegerField(source="test_questions.count", read_only=True)

    class Meta:
        model = OnlineTest
        fields = [
            "id",
            "school_id",
            "academic_year",
            "academic_class",
            "section",
            "subject", "subject_code",
            "title",
            "start_at", "end_at", "duration_minutes",
            "total_marks", "attempt_limit",
            "shuffle_questions", "shuffle_choices",
            "is_published",
            "created_at",
            "class_name", "section_name",
            "test_questions_count",
        ]
        read_only_fields = ["id", "school_id", "total_marks", "is_published", "created_at"]

    def validate(self, attrs):
        request = self.context["request"]
        school_id = request.school_id

        year = attrs.get("academic_year") or getattr(self.instance, "academic_year", None)
        cls = attrs.get("academic_class") or getattr(self.instance, "academic_class", None)
        sec = attrs.get("section") if "section" in attrs else getattr(self.instance, "section", None)
        subject = attrs.get("subject") or getattr(self.instance, "subject", None)
        start_at = attrs.get("start_at") or getattr(self.instance, "start_at", None)
        end_at = attrs.get("end_at") or getattr(self.instance, "end_at", None)

        if year and year.school_id != school_id:
            raise serializers.ValidationError({"academic_year": "Academic year not in this school."})
        if cls and cls.school_id != school_id:
            raise serializers.ValidationError({"academic_class": "Class not in this school."})
        if year and cls and cls.academic_year_id != year.id:
            raise serializers.ValidationError({"academic_class": "Class does not belong to academic year."})
        if sec and cls and sec.academic_class_id != cls.id:
            raise serializers.ValidationError({"section": "Section does not belong to class."})
        if subject and subject.school_id != school_id:
            raise serializers.ValidationError({"subject": "Subject not in this school."})

        if start_at and end_at and start_at >= end_at:
            raise serializers.ValidationError({"end_at": "end_at must be after start_at."})

        # If already published, lock some fields unless you decide otherwise
        if self.instance and self.instance.is_published:
            locked = ["academic_year", "academic_class", "section", "subject", "start_at", "end_at", "duration_minutes"]
            for f in locked:
                if f in attrs:
                    raise serializers.ValidationError({f: "Cannot modify this field after publish. Unpublish first."})

        return attrs


class TestQuestionSerializer(serializers.ModelSerializer):
    question_text = serializers.CharField(source="question.text", read_only=True)
    qtype = serializers.CharField(source="question.qtype", read_only=True)

    class Meta:
        model = TestQuestion
        fields = ["id", "test", "question", "question_text", "qtype", "order", "marks_override"]
        read_only_fields = ["id"]


class AddQuestionToTestSerializer(serializers.Serializer):
    test_id = serializers.UUIDField()
    question_id = serializers.UUIDField()
    order = serializers.IntegerField(required=False, default=0)
    marks_override = serializers.DecimalField(max_digits=6, decimal_places=2, required=False)

    def validate(self, attrs):
        request = self.context["request"]
        school_id = request.school_id

        test = OnlineTest.objects.select_related("subject").filter(id=attrs["test_id"], school_id=school_id).first()
        if not test:
            raise serializers.ValidationError({"test_id": "Test not found in this school."})

        q = Question.objects.select_related("bank__subject").filter(id=attrs["question_id"]).first()
        if not q:
            raise serializers.ValidationError({"question_id": "Question not found."})
        if q.bank.school_id != school_id:
            raise serializers.ValidationError({"question_id": "Question not in this school."})

        # Optional strictness: ensure subject matches
        if q.bank.subject_id != test.subject_id:
            raise serializers.ValidationError({"question_id": "Question subject must match test subject."})

        if test.is_published:
            raise serializers.ValidationError("Cannot modify questions after publish. Unpublish first.")

        attrs["_test"] = test
        attrs["_question"] = q
        return attrs

    def create(self, validated_data):
        test = validated_data["_test"]
        q = validated_data["_question"]

        obj, created = TestQuestion.objects.get_or_create(
            test=test,
            question=q,
            defaults={
                "order": validated_data.get("order", 0),
                "marks_override": validated_data.get("marks_override"),
            },
        )
        if not created:
            # if exists, update order/override
            obj.order = validated_data.get("order", obj.order)
            if "marks_override" in validated_data:
                obj.marks_override = validated_data.get("marks_override")
            obj.save(update_fields=["order", "marks_override"])

        return obj


class ReorderQuestionsSerializer(serializers.Serializer):
    test_id = serializers.UUIDField()
    items = serializers.ListField(
        child=serializers.DictField(),
        min_length=1,
        help_text="Each item: {test_question_id: uuid, order: int}"
    )

    def validate(self, attrs):
        request = self.context["request"]
        school_id = request.school_id
        test = OnlineTest.objects.filter(id=attrs["test_id"], school_id=school_id).first()
        if not test:
            raise serializers.ValidationError({"test_id": "Test not found."})
        if test.is_published:
            raise serializers.ValidationError("Cannot reorder after publish. Unpublish first.")
        attrs["_test"] = test
        return attrs

    def create(self, validated_data):
        test = validated_data["_test"]
        id_order = {}
        for it in validated_data["items"]:
            tid = str(it.get("test_question_id") or "")
            if not tid:
                continue
            id_order[tid] = int(it.get("order") or 0)

        qs = TestQuestion.objects.filter(test=test)
        for tq in qs:
            new_order = id_order.get(str(tq.id))
            if new_order is not None and tq.order != new_order:
                tq.order = new_order
                tq.save(update_fields=["order"])

        return test


def recalc_test_total_marks(test: OnlineTest):
    total = Decimal("0.00")
    for tq in test.test_questions.select_related("question").all():
        total += Decimal(str(tq.marks_override)) if tq.marks_override is not None else Decimal(str(tq.question.marks))
    test.total_marks = total
    test.save(update_fields=["total_marks"])
