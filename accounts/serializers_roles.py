from rest_framework import serializers
from accounts.models import Role, RoleAssignment

class RoleSerializer(serializers.ModelSerializer):
    class Meta:
        model = Role
        fields = ["id", "school_id", "code", "name", "is_system"]
        read_only_fields = ["id"]

class RoleAssignmentSerializer(serializers.ModelSerializer):
    role_code = serializers.CharField(source="role.code", read_only=True)
    role_name = serializers.CharField(source="role.name", read_only=True)
    user_email = serializers.EmailField(source="user.email", read_only=True)

    class Meta:
        model = RoleAssignment
        fields = [
            "id", "user", "user_email", "role", "role_code", "role_name",
            "scope_type", "scope_id", "valid_from", "valid_to", "created_at",
        ]
        read_only_fields = ["id", "created_at"]
