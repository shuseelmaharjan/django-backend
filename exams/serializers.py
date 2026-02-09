from django.db import transaction
from rest_framework import serializers

from exams.models import Exam, ExamSet, Section, Question, AnswerOption


# =========================
# Exam (Admin-managed)
# =========================

class ExamReadSerializer(serializers.ModelSerializer):
    class Meta:
        model = Exam
        fields = [
            "id",
            "title",
            "category",
            "batch",
            "exam_year",
            "sort_order",
            "is_active",
            "created_at",
            "updated_at",
        ]


class ExamCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = Exam
        fields = [
            "title",
            "category",
            "batch",
            "exam_year",
            "sort_order",
            "is_active",
        ]


class ExamUpdateSerializer(serializers.ModelSerializer):
    class Meta:
        model = Exam
        fields = [
            "title",
            "category",
            "batch",
            "exam_year",
            "sort_order",
            "is_active",
        ]


class ExamReorderSerializer(serializers.Serializer):
    """
    payload: { "items": [ {"id": "<uuid>", "sort_order": 1}, ... ] }
    """
    items = serializers.ListField(
        child=serializers.DictField(),
        allow_empty=False
    )

    def validate_items(self, items):
        for i in items:
            if "id" not in i or "sort_order" not in i:
                raise serializers.ValidationError("Each item must have id and sort_order.")
        return items


class ExamToggleActiveSerializer(serializers.Serializer):
    is_active = serializers.BooleanField()


# =========================
# ExamSet tree (Teacher-managed)
# =========================

class AnswerOptionReadSerializer(serializers.ModelSerializer):
    class Meta:
        model = AnswerOption
        fields = ["id", "text", "is_correct", "sort_order", "is_active", "created_at", "updated_at"]


class AnswerOptionWriteSerializer(serializers.ModelSerializer):
    id = serializers.IntegerField(required=False)

    class Meta:
        model = AnswerOption
        fields = ["id", "text", "is_correct", "sort_order", "is_active"]


class QuestionReadSerializer(serializers.ModelSerializer):
    answer_options = AnswerOptionReadSerializer(many=True, read_only=True)

    class Meta:
        model = Question
        fields = [
            "id", "text", "question_type", "media", "marks",
            "sort_order", "is_active",
            "answer_options",
            "created_at", "updated_at",
        ]


class QuestionWriteSerializer(serializers.ModelSerializer):
    id = serializers.UUIDField(required=False)
    answer_options = AnswerOptionWriteSerializer(many=True, required=False)

    class Meta:
        model = Question
        fields = ["id", "text", "question_type", "media", "marks", "sort_order", "is_active", "answer_options"]

    def validate(self, attrs):
        opts = self.initial_data.get("answer_options")
        if isinstance(opts, list) and sum(1 for o in opts if o.get("is_correct")) > 1:
            raise serializers.ValidationError({"answer_options": "Only one option can be correct."})
        return attrs


class SectionReadSerializer(serializers.ModelSerializer):
    questions = QuestionReadSerializer(many=True, read_only=True)

    class Meta:
        model = Section
        fields = [
            "id", "title", "instructions", "question_type", "media",
            "sort_order", "is_active",
            "questions",
            "created_at", "updated_at",
        ]


class SectionWriteSerializer(serializers.ModelSerializer):
    id = serializers.UUIDField(required=False)
    questions = QuestionWriteSerializer(many=True, required=False)

    class Meta:
        model = Section
        fields = [
            "id", "title", "instructions", "question_type", "media",
            "sort_order", "is_active",
            "questions",
        ]


class ExamSetReadSerializer(serializers.ModelSerializer):
    sections = SectionReadSerializer(many=True, read_only=True)

    class Meta:
        model = ExamSet
        fields = [
            "id", "set_by", "exam", "academic_class", "subject",
            "title", "num_of_questions", "exam_duration_minutes",
            "instructions", "status", "sort_order",
            "sections",
            "created_at", "updated_at",
        ]


class ExamSetCreateSerializer(serializers.ModelSerializer):
    sections = SectionWriteSerializer(many=True, required=False)
    set_by = serializers.PrimaryKeyRelatedField(read_only=True)

    class Meta:
        model = ExamSet
        fields = [
            "set_by", "exam", "academic_class", "subject",
            "title", "num_of_questions", "exam_duration_minutes",
            "instructions", "status", "sort_order",
            "sections",
        ]


class ExamSetUpdateSerializer(serializers.ModelSerializer):
    id = serializers.UUIDField(required=False)
    sections = SectionWriteSerializer(many=True, required=False)
    set_by = serializers.PrimaryKeyRelatedField(read_only=True)

    class Meta:
        model = ExamSet
        fields = [
            "id", "set_by", "exam", "academic_class", "subject",
            "title", "num_of_questions", "exam_duration_minutes",
            "instructions", "status", "sort_order",
            "sections",
        ]


class ExamSetReorderSerializer(serializers.Serializer):
    items = serializers.ListField(child=serializers.DictField(), allow_empty=False)

    def validate_items(self, items):
        for i in items:
            if "id" not in i or "sort_order" not in i:
                raise serializers.ValidationError("Each item must have id and sort_order.")
        return items


class ExamSetStatusToggleSerializer(serializers.Serializer):
    status = serializers.CharField(max_length=20)
