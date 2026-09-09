from rest_framework import serializers

from apps.organizations.models import Organization, MemberShip, OrganizationSettings


class OrganizationSerializer(serializers.ModelSerializer):
    class Meta:
        model = Organization
        fields = ["id", "name", "slug", "status", "created_at", "updated_at"]
        read_only_fields = ["id", "slug", "status", "created_at", "updated_at"]


class OrganizationCreateSerializer(serializers.Serializer):
    """
    Separate from OrganizationSerializer since creation only accepts
    `name` — slug/status/owner are all derived server-side, never
    accepted from the client.
    """

    name = serializers.CharField(max_length=255)


class MembershipSerializer(serializers.ModelSerializer):
    user_email = serializers.EmailField(source="user.email", read_only=True)

    class Meta:
        model = MemberShip
        fields = [
            "id",
            "user",
            "user_email",
            "role",
            "status",
            "joined_at",
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "id",
            "user",
            "user_email",
            "status",
            "joined_at",
            "created_at",
            "updated_at",
        ]


class MembershipRoleUpdateSerializer(serializers.Serializer):
    """
    Only `role` is patchable through this endpoint — status changes
    (e.g. suspending a member) are a separate concern, not handled by
    change_member_role().
    """

    role = serializers.ChoiceField(choices=MemberShip.Role.choices)


class OrganizationSettingsSerializer(serializers.ModelSerializer):
    class Meta:
        model = OrganizationSettings
        fields = [
            "id",
            "default_task_status",
            "allow_public_signup",
            "custom_branding",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "created_at", "updated_at"]
