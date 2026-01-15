from rest_framework import serializers
from accounts.models import Role, RoleAssignment
from common.constants import ScopeType


class RoleSerializer(serializers.ModelSerializer):
    code = serializers.CharField()

    class Meta:
        model = Role
        fields = ["id", "school_id", "code", "name", "is_system"]
        read_only_fields = ["id"]

    def validate_code(self, value: str):
        value = (value or "").strip().lower()
        if not value:
            raise serializers.ValidationError("Role code is required.")
        return value


class RoleAssignmentSerializer(serializers.ModelSerializer):
    role_code = serializers.CharField(source="role.code", read_only=True)
    role_name = serializers.CharField(source="role.name", read_only=True)
    user_email = serializers.EmailField(source="user.email", read_only=True)

    class Meta:
        model = RoleAssignment
        fields = [
            "id",
            "user",
            "user_email",
            "role",
            "role_code",
            "role_name",
            "scope_type",
            "scope_id",
            "valid_from",
            "valid_to",
            "created_at",
        ]
        read_only_fields = ["id", "created_at", "user_email", "role_code", "role_name"]

    def validate(self, attrs):
        scope_type = attrs.get("scope_type") or getattr(self.instance, "scope_type", None)
        scope_id = attrs.get("scope_id") if "scope_id" in attrs else getattr(self.instance, "scope_id", "")

        scope_id = (scope_id or "").strip()

        if scope_type and scope_type != ScopeType.GLOBAL:
            # for non-global, "*" is not meaningful (unless you intentionally support it)
            if not scope_id or scope_id == "*":
                raise serializers.ValidationError({"scope_id": "scope_id is required for non-global scopes."})

        valid_from = attrs.get("valid_from") if "valid_from" in attrs else getattr(self.instance, "valid_from", None)
        valid_to = attrs.get("valid_to") if "valid_to" in attrs else getattr(self.instance, "valid_to", None)

        if valid_from and valid_to and valid_from > valid_to:
            raise serializers.ValidationError({"valid_to": "valid_to must be after valid_from."})

        return attrs
