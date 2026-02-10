import uuid

from django.core.validators import MinValueValidator, MaxValueValidator
from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import Q


class ExamCategory(models.TextChoices):
    EPS = "eps", "EPS"


class ExamSetStatus(models.TextChoices):
    DRAFT = "draft", "Draft"
    PUBLISHED = "published", "Published"
    ARCHIVED = "archived", "Archived"


class QuestionType(models.TextChoices):
    TEXT = "text", "Text Based"
    IMAGE = "image", "Image Based"
    AUDIO = "audio", "Audio Based"


def validate_audio(value):
    if not value.name.endswith(".mp3"):
        raise ValidationError("Only MP3 files are allowed.")


def validate_image(value):
    if not value.name.endswith((".jpg", ".png")):
        raise ValidationError("Only JPG or PNG files are allowed.")


class Exam(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    title = models.CharField(max_length=100)
    category = models.CharField(
        max_length=10,
        choices=ExamCategory.choices,
        default=ExamCategory.EPS,
        db_index=True,
    )
    batch = models.ForeignKey(
        "batch.AcademicBatch",
        on_delete=models.CASCADE,
        related_name="exams",
        db_index=True,
        null=True,
        blank=True,
    )
    exam_year = models.PositiveSmallIntegerField(
        validators=[MinValueValidator(2000), MaxValueValidator(2100)]
    )
    sort_order = models.PositiveSmallIntegerField(default=0)
    is_active = models.BooleanField(default=True, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        indexes = [
            models.Index(fields=["batch", "exam_year", "category"]),
        ]
        ordering = ["sort_order", "-created_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["batch", "exam_year", "category"],
                name="unique_exam_per_batch_year_category",
                condition=Q(batch__isnull=False)
            )
        ]


class ExamSet(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    set_by = models.ForeignKey(
        "accounts.User",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="exam_sets"
    )
    exam = models.ForeignKey(
        Exam,
        on_delete=models.CASCADE,
        related_name="exam_sets"
    )
    academic_class = models.ForeignKey(
        "academics.AcademicClass",
        on_delete=models.CASCADE,
        related_name="exam_sets",
    )
    subject = models.ForeignKey(
        "subjects.Subject",
        on_delete=models.CASCADE,
        related_name="exam_sets"
    )
    title = models.CharField(max_length=100)
    num_of_questions = models.PositiveIntegerField()
    exam_duration_minutes = models.PositiveIntegerField()
    instructions = models.TextField(blank=True)
    status = models.CharField(
        max_length=20,
        choices=ExamSetStatus.choices,
        default=ExamSetStatus.DRAFT,
    )
    sort_order = models.PositiveSmallIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        indexes = [
            models.Index(fields=["exam", "subject", "academic_class", "status"]),
        ]
        ordering = ["sort_order", "created_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["exam", "subject", "academic_class"],
                name="unique_exam_set_per_exam_subject_academic_class",
            )
        ]


class Section(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    exam_set = models.ForeignKey(
        ExamSet,
        related_name="sections",
        on_delete=models.CASCADE
    )
    title = models.CharField(max_length=100)
    instructions = models.TextField(blank=True)
    question_type = models.CharField(
        max_length=20,
        choices=QuestionType.choices,
        default=QuestionType.TEXT,
    )
    media = models.ForeignKey(
        "filehandler.UploadedFile",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="section_media_files",
        validators=[validate_audio, validate_image],
    )
    sort_order = models.PositiveSmallIntegerField(default=0)
    is_active = models.BooleanField(default=True, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        indexes = [
            models.Index(fields=["exam_set", "sort_order"]),
        ]
        ordering = ["sort_order", "created_at"]


class Question(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    section = models.ForeignKey(
        Section,
        related_name="questions",
        on_delete=models.CASCADE
    )
    text = models.TextField(max_length=2000)
    question_type = models.CharField(
        max_length=20,
        choices=QuestionType.choices,
        default=QuestionType.TEXT,
    )
    media = models.ForeignKey(
        "filehandler.UploadedFile",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="question_media_files",
        validators=[validate_audio, validate_image],
    )
    marks = models.PositiveIntegerField(default=5)
    sort_order = models.PositiveSmallIntegerField(default=0)
    is_active = models.BooleanField(default=True, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        indexes = [
            models.Index(fields=["section", "sort_order"]),
        ]
        ordering = ["sort_order", "created_at"]


class AnswerOption(models.Model):
    id = models.AutoField(primary_key=True)
    question = models.ForeignKey(
        Question,
        related_name="answer_options",
        on_delete=models.CASCADE
    )
    text = models.CharField(max_length=100)
    is_correct = models.BooleanField(default=False)
    sort_order = models.PositiveSmallIntegerField(default=0)
    is_active = models.BooleanField(default=True, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        indexes = [
            models.Index(fields=["question", "sort_order"]),
        ]
        ordering = ["sort_order", "created_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["question"],
                condition=models.Q(is_correct=True),
                name="one_correct_answer_per_question"
            )
        ]
