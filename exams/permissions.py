from rest_framework.permissions import BasePermission

from profiles.models import TeacherSpecialization


class IsSubjectTeacher(BasePermission):
    """
    Teacher allowed only if request.user is specialized for obj.subject.
    Works for ExamSet object-level checks.
    """
    message = "You are not assigned to this subject."

    def has_object_permission(self, request, view, obj):
        user = request.user
        if not getattr(user, "is_teacher", False):
            return False

        return TeacherSpecialization.objects.filter(
            user=user,
            subjects=obj.subject,
        ).exists()