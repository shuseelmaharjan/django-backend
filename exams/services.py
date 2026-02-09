from django.db import transaction
from django.core.exceptions import PermissionDenied

from exams.models import Exam, ExamSet, Section, Question, AnswerOption
from profiles.models import TeacherSpecialization


class ExamService:
    @staticmethod
    def create_exam(payload: dict) -> Exam:
        return Exam.objects.create(**payload)

    @staticmethod
    def update_exam(exam: Exam, payload: dict) -> Exam:
        for k, v in payload.items():
            setattr(exam, k, v)
        exam.save()
        return exam

    @staticmethod
    def soft_delete_exam(exam: Exam) -> None:
        exam.is_active = False
        exam.save(update_fields=["is_active", "updated_at"])

    @staticmethod
    @transaction.atomic
    def reorder(items: list[dict]) -> None:
        # items: [{"id": uuid, "sort_order": int}, ...]
        ids = [i["id"] for i in items]
        obj_map = {str(o.id): o for o in Exam.objects.filter(id__in=ids)}
        for item in items:
            obj = obj_map.get(str(item["id"]))
            if obj:
                obj.sort_order = int(item["sort_order"])
                obj.save(update_fields=["sort_order", "updated_at"])

    @staticmethod
    def set_active(exam: Exam, is_active: bool) -> Exam:
        exam.is_active = bool(is_active)
        exam.save(update_fields=["is_active", "updated_at"])
        return exam


class ExamSetService:
    @staticmethod
    def _ensure_teacher_can_use_subject(*, teacher, subject):
        if getattr(teacher, "is_staff", False):
            return
        if not getattr(teacher, "is_teacher", False):
            raise PermissionDenied("Only teachers can manage exam sets.")
        allowed = TeacherSpecialization.objects.filter(user=teacher, subjects=subject).exists()
        if not allowed:
            raise PermissionDenied("You are not assigned for this subject.")

    @staticmethod
    @transaction.atomic
    def create_examset(payload: dict, teacher) -> ExamSet:
        sections_data = payload.pop("sections", [])
        subject = payload.get("subject")

        # Enforce specialization BEFORE create
        ExamSetService._ensure_teacher_can_use_subject(teacher=teacher, subject=subject)

        payload["set_by"] = teacher
        exam_set = ExamSet.objects.create(**payload)

        for sec in sections_data:
            questions_data = sec.pop("questions", [])
            section = Section.objects.create(exam_set=exam_set, **sec)

            for q in questions_data:
                opts_data = q.pop("answer_options", [])
                question = Question.objects.create(section=section, **q)

                for opt in opts_data:
                    AnswerOption.objects.create(question=question, **opt)

        return exam_set

    @staticmethod
    @transaction.atomic
    def update_examset(exam_set: ExamSet, payload: dict, teacher) -> ExamSet:
        # Must be allowed for the existing subject
        ExamSetService._ensure_teacher_can_use_subject(teacher=teacher, subject=exam_set.subject)

        # prevent changing subject/exam on update
        payload.pop("set_by", None)
        payload.pop("subject", None)
        payload.pop("exam", None)

        sections_data = payload.pop("sections", None)

        for k, v in payload.items():
            setattr(exam_set, k, v)
        exam_set.save()

        if sections_data is None:
            return exam_set

        existing_sections = {str(s.id): s for s in exam_set.sections.all()}
        kept_section_ids = set()

        for sec in sections_data:
            sec_id = str(sec.get("id")) if sec.get("id") else None
            questions_data = sec.pop("questions", [])

            if sec_id and sec_id in existing_sections:
                section = existing_sections[sec_id]
                for k, v in sec.items():
                    if k != "id":
                        setattr(section, k, v)
                section.save()
            else:
                section = Section.objects.create(
                    exam_set=exam_set, **{k: v for k, v in sec.items() if k != "id"}
                )

            kept_section_ids.add(str(section.id))

            existing_questions = {str(q.id): q for q in section.questions.all()}
            kept_question_ids = set()

            for q in questions_data:
                q_id = str(q.get("id")) if q.get("id") else None
                opts_data = q.pop("answer_options", [])

                if q_id and q_id in existing_questions:
                    question = existing_questions[q_id]
                    for k, v in q.items():
                        if k != "id":
                            setattr(question, k, v)
                    question.save()
                else:
                    question = Question.objects.create(
                        section=section, **{k: v for k, v in q.items() if k != "id"}
                    )

                kept_question_ids.add(str(question.id))

                existing_opts = {str(o.id): o for o in question.answer_options.all()}
                kept_opt_ids = set()

                for opt in opts_data:
                    opt_id = str(opt.get("id")) if opt.get("id") else None

                    if opt_id and opt_id in existing_opts:
                        option = existing_opts[opt_id]
                        for k, v in opt.items():
                            if k != "id":
                                setattr(option, k, v)
                        option.save()
                    else:
                        option = AnswerOption.objects.create(
                            question=question, **{k: v for k, v in opt.items() if k != "id"}
                        )

                    kept_opt_ids.add(str(option.id))

                for oid, obj in existing_opts.items():
                    if oid not in kept_opt_ids:
                        obj.delete()

            for qid, obj in existing_questions.items():
                if qid not in kept_question_ids:
                    obj.delete()

        for sid, obj in existing_sections.items():
            if sid not in kept_section_ids:
                obj.delete()

        return exam_set

    @staticmethod
    def delete_examset(exam_set: ExamSet, teacher) -> None:
        # enforce allowed
        ExamSetService._ensure_teacher_can_use_subject(teacher=teacher, subject=exam_set.subject)
        exam_set.delete()
