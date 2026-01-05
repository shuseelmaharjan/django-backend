# assessments/models.py
import uuid
from django.db import models
from django.utils import timezone

class QuestionType(models.TextChoices):
    MCQ = "mcq", "MCQ"
    TRUE_FALSE = "tf", "True/False"
    SHORT = "short", "Short"
    LONG = "long", "Long"


class AttemptStatus(models.TextChoices):
    IN_PROGRESS = "in_progress", "In Progress"
    SUBMITTED = "submitted", "Submitted"
    EVALUATED = "evaluated", "Evaluated"


class Subject(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    school_id = models.CharField(max_length=64, db_index=True)
    code = models.SlugField(max_length=50)
    name = models.CharField(max_length=120)
    is_active = models.BooleanField(default=True)

    class Meta:
        unique_together = ("school_id", "code")
        indexes = [models.Index(fields=["school_id", "is_active"])]

    def __str__(self):
        return self.name


class QuestionBank(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    school_id = models.CharField(max_length=64, db_index=True)
    subject = models.ForeignKey(Subject, on_delete=models.CASCADE, related_name="banks")
    topic = models.CharField(max_length=120, blank=True, default="")
    difficulty = models.CharField(max_length=20, blank=True, default="")  # easy/med/hard
    is_active = models.BooleanField(default=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["school_id", "subject", "topic", "difficulty"],
                name="uq_bank_school_subject_topic_difficulty",
            )
        ]
        indexes = [
            models.Index(fields=["school_id", "subject"]),
        ]

    def __str__(self):
        return f"{self.subject.name} Bank"


class Question(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    bank = models.ForeignKey(QuestionBank, on_delete=models.CASCADE, related_name="questions")

    qtype = models.CharField(max_length=20, choices=QuestionType.choices, db_index=True)
    text = models.TextField()
    marks = models.DecimalField(max_digits=6, decimal_places=2, default="1.00")

    explanation = models.TextField(blank=True, default="")
    attachment_file = models.ForeignKey(
        "filehandler.UploadedFile",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="+",
    )

    is_active = models.BooleanField(default=True)

    def __str__(self):
        return f"{self.qtype} - {self.marks}"


class QuestionChoice(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    question = models.ForeignKey(Question, on_delete=models.CASCADE, related_name="choices")
    text = models.CharField(max_length=255)
    is_correct = models.BooleanField(default=False)

    class Meta:
        indexes = [models.Index(fields=["question", "is_correct"])]


class OnlineTest(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    school_id = models.CharField(max_length=64, db_index=True)
    academic_year = models.ForeignKey("academics.AcademicYear", on_delete=models.CASCADE, related_name="online_tests")

    academic_class = models.ForeignKey("academics.AcademicClass", on_delete=models.CASCADE, related_name="online_tests")
    section = models.ForeignKey("academics.Section", on_delete=models.SET_NULL, null=True, blank=True, related_name="online_tests")

    subject = models.ForeignKey(Subject, on_delete=models.PROTECT, related_name="online_tests")

    title = models.CharField(max_length=200)
    start_at = models.DateTimeField()
    end_at = models.DateTimeField()
    duration_minutes = models.PositiveIntegerField(default=60)

    total_marks = models.DecimalField(max_digits=8, decimal_places=2, default="0.00")
    attempt_limit = models.PositiveIntegerField(default=1)

    shuffle_questions = models.BooleanField(default=True)
    shuffle_choices = models.BooleanField(default=True)

    is_published = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        indexes = [
            models.Index(fields=["school_id", "academic_year", "academic_class", "section"]),
            models.Index(fields=["is_published", "start_at"]),
        ]

    def __str__(self):
        return self.title


class TestQuestion(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    test = models.ForeignKey(OnlineTest, on_delete=models.CASCADE, related_name="test_questions")
    question = models.ForeignKey(Question, on_delete=models.PROTECT, related_name="in_tests")

    order = models.PositiveIntegerField(default=0)
    marks_override = models.DecimalField(max_digits=6, decimal_places=2, null=True, blank=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["test", "question"], name="uq_test_question"),
        ]
        ordering = ["order"]


class StudentTestAttempt(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    test = models.ForeignKey(OnlineTest, on_delete=models.CASCADE, related_name="attempts")
    student = models.ForeignKey("students.StudentProfile", on_delete=models.CASCADE, related_name="test_attempts")

    attempt_no = models.PositiveIntegerField(default=1)
    started_at = models.DateTimeField(default=timezone.now)
    submitted_at = models.DateTimeField(null=True, blank=True)

    status = models.CharField(max_length=20, choices=AttemptStatus.choices, default=AttemptStatus.IN_PROGRESS, db_index=True)
    score = models.DecimalField(max_digits=8, decimal_places=2, default="0.00")

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["test", "student", "attempt_no"], name="uq_test_student_attempt"),
        ]
        indexes = [
            models.Index(fields=["student", "status"]),
            models.Index(fields=["test", "status"]),
        ]


class StudentAnswer(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    attempt = models.ForeignKey(StudentTestAttempt, on_delete=models.CASCADE, related_name="answers")
    question = models.ForeignKey(Question, on_delete=models.PROTECT, related_name="+")
    selected_choice = models.ForeignKey(QuestionChoice, on_delete=models.SET_NULL, null=True, blank=True, related_name="+")
    answer_text = models.TextField(blank=True, default="")

    is_correct = models.BooleanField(default=False)
    marks_awarded = models.DecimalField(max_digits=6, decimal_places=2, default="0.00")

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["attempt", "question"], name="uq_attempt_question_answer"),
        ]
