# profiles/serializers_teacher_list.py
from rest_framework import serializers
from accounts.models import User
from profiles.models import Profile, TeacherSpecialization

class TeacherListSerializer(serializers.ModelSerializer):
    full_name = serializers.SerializerMethodField()
    teacher_level = serializers.SerializerMethodField()
    teacher_level_id = serializers.SerializerMethodField()
    profile_id = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = [
            "id",
            "phone",
            "email",
            "role",
            "status",
            "first_name",
            "middle_name",
            "last_name",
            "full_name",
            "profile_id",
            "teacher_level_id",
            "teacher_level",
        ]

    def get_full_name(self, obj: User) -> str:
        parts = [obj.first_name, getattr(obj, "middle_name", ""), obj.last_name]
        return " ".join([p for p in parts if p]).strip()

    def get_profile_id(self, obj: User):
        # Profile is OneToOne: user.profile
        prof = getattr(obj, "profile", None)
        return getattr(prof, "id", None)

    def get_teacher_level_id(self, obj: User):
        spec = getattr(obj, "_teacher_spec", None)
        if spec and spec.teacher_level_id:
            return spec.teacher_level_id
        return None

    def get_teacher_level(self, obj: User):
        spec = getattr(obj, "_teacher_spec", None)
        if spec and spec.teacher_level:
            return spec.teacher_level.level
        return None
