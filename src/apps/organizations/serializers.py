from rest_framework import serializers

from apps.organizations.models import (
    Organization,
    MemberShip,
    OrganizationSettings,
    OrganizationInvitation,
)


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


# ================== invitation serializers ==================


class InvitationCreateSerializer(serializers.Serializer):
    email = serializers.EmailField(max_length=255)
    role = serializers.ChoiceField(choices=OrganizationInvitation.InvitableRole.choices)

    def validate_email(self, value):
        """
        normalize the email to lowercase and validate that it is not already a member of the organization.
        """
        value = value.lower()
        organization = self.context["organization"]
        if organization.memberships.filter(
            user__email=value, status=MemberShip.Status.ACTIVE
        ).exists():
            raise serializers.ValidationError(
                "This user is already a member of the organization."
            )

        if organization.invitations.filter(
            email=value, status=OrganizationInvitation.Status.PENDING
        ).exists():
            raise serializers.ValidationError(
                "This user has already been invited to the organization."
            )
        return value


class InvitationSerializer(serializers.ModelSerializer):
    class Meta:
        model = OrganizationInvitation
        fields = [
            "id",
            "email",
            "role",
            "status",
            "invited_by",
            "expires_at",
            "created_at",
        ]
        read_only_fields = [
            "id",
            "email",
            "status",
            "role",
            "invited_by",
            "expires_at",
            "created_at",
        ]


class AcceptInvitationSerializer(serializers.Serializer):
    token = serializers.CharField(max_length=255)
