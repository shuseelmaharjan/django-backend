from decimal import Decimal
from rest_framework import serializers
from assessments.models import Subject, QuestionBank, Question, QuestionChoice, QuestionType


class QuestionBankSerializer(serializers.ModelSerializer):
    subject_code = serializers.CharField(source="subject.code", read_only=True)
    subject_name = serializers.CharField(source="subject.name", read_only=True)

    class Meta:
        model = QuestionBank
        fields = [
            "id", "school_id",
            "subject", "subject_code", "subject_name",
            "topic", "difficulty",
            "is_active",
        ]
        read_only_fields = ["id", "school_id"]

    def validate(self, attrs):
        request = self.context["request"]
        school_id = request.school_id
        subject = attrs.get("subject") or getattr(self.instance, "subject", None)

        if subject and subject.school_id != school_id:
            raise serializers.ValidationError({"subject": "Subject not in this school."})
        return attrs


class QuestionChoiceSerializer(serializers.ModelSerializer):
    class Meta:
        model = QuestionChoice
        fields = ["id", "question", "text", "is_correct"]
        read_only_fields = ["id"]


class QuestionSerializer(serializers.ModelSerializer):
    choices = QuestionChoiceSerializer(many=True, read_only=True)

    class Meta:
        model = Question
        fields = [
            "id",
            "bank",
            "qtype",
            "text",
            "marks",
            "explanation",
            "attachment_file",
            "is_active",
            "choices",
        ]
        read_only_fields = ["id"]

    def validate_marks(self, v):
        try:
            dv = Decimal(str(v))
        except Exception:
            raise serializers.ValidationError("Invalid marks.")
        if dv <= 0:
            raise serializers.ValidationError("Marks must be > 0.")
        return v

    def validate(self, attrs):
        qtype = attrs.get("qtype") or getattr(self.instance, "qtype", None)
        bank = attrs.get("bank") or getattr(self.instance, "bank", None)
        request = self.context["request"]
        school_id = request.school_id

        if bank and bank.school_id != school_id:
            raise serializers.ValidationError({"bank": "Question bank not in this school."})

        if qtype not in dict(QuestionType.choices):
            raise serializers.ValidationError({"qtype": "Invalid question type."})

        return attrs


class QuestionChoiceBulkUpsertSerializer(serializers.Serializer):
    """
    Upsert choices for a question in one call.
    Only valid for MCQ/TF.
    """
    question_id = serializers.UUIDField()
    choices = serializers.ListField(
        child=serializers.DictField(),
        min_length=2,
        help_text="Each item: {text: str, is_correct: bool, id?: uuid}"
    )

    def validate(self, attrs):
        request = self.context["request"]
        school_id = request.school_id

        q = Question.objects.select_related("bank").filter(id=attrs["question_id"]).first()
        if not q:
            raise serializers.ValidationError({"question_id": "Question not found."})
        if q.bank.school_id != school_id:
            raise serializers.ValidationError({"question_id": "Question not in this school."})

        if q.qtype not in (QuestionType.MCQ, QuestionType.TRUE_FALSE):
            raise serializers.ValidationError("Choices can only be set for MCQ/True-False questions.")

        correct_count = sum(1 for c in attrs["choices"] if bool(c.get("is_correct")))
        if correct_count < 1:
            raise serializers.ValidationError("At least 1 correct choice is required.")

        # Optional strictness: TF must have exactly 2 choices
        if q.qtype == QuestionType.TRUE_FALSE and len(attrs["choices"]) != 2:
            raise serializers.ValidationError("True/False question must have exactly 2 choices.")

        attrs["_question"] = q
        return attrs

    def create(self, validated_data):
        q = validated_data["_question"]
        incoming = validated_data["choices"]

        # Strategy: delete & recreate is simplest; but we can upsert safely.
        # We'll upsert by ID if provided, else create.
        existing = {str(c.id): c for c in q.choices.all()}
        keep_ids = set()

        for item in incoming:
            cid = str(item.get("id") or "")
            text = (item.get("text") or "").strip()
            if not text:
                continue
            is_correct = bool(item.get("is_correct"))

            if cid and cid in existing:
                obj = existing[cid]
                obj.text = text
                obj.is_correct = is_correct
                obj.save(update_fields=["text", "is_correct"])
                keep_ids.add(obj.id)
            else:
                obj = QuestionChoice.objects.create(question=q, text=text, is_correct=is_correct)
                keep_ids.add(obj.id)

        # remove any old choices not in keep_ids
        q.choices.exclude(id__in=keep_ids).delete()

        return q
