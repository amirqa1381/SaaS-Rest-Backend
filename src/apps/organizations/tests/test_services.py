import pytest
from unittest.mock import patch

from apps.organizations.models import Organization, MemberShip
from apps.organizations.services import (
    create_organization,
    update_organization,
    update_organization_settings,
    change_member_role,
    remove_member,
    leave_organization,
    NotAMemberError,
    InsufficientRoleError,
    CannotRemoveLastOwnerError,
    CannotActOnSelfError,
)
from .factories import UserFactory, OrganizationFactory, MembershipFactory

pytestmark = pytest.mark.django_db


# ---------------------------------------------------------------------------
# create_organization
# ---------------------------------------------------------------------------

class TestCreateOrganization:
    def test_creates_organization_with_given_name(self, user_a):
        org = create_organization(owner=user_a, name="Acme")
        assert org.name == "Acme"
        assert org.pk is not None

    def test_creates_founding_owner_membership(self, user_a):
        org = create_organization(owner=user_a, name="Acme")
        membership = MemberShip.objects.get(organization=org, user=user_a)
        assert membership.role == MemberShip.Role.OWNER
        assert membership.status == MemberShip.Status.ACTIVE

    def test_returns_the_created_organization(self, user_a):
        org = create_organization(owner=user_a, name="Acme")
        assert isinstance(org, Organization)

    def test_is_atomic_org_not_persisted_if_membership_creation_fails(self, user_a):
        """
        Per architecture doc §18 ADR #1: an org with zero owners must
        never be an observable state. If the Membership create fails,
        the Organization row must not exist either.
        """
        with patch(
            "apps.organizations.services.MemberShip.objects.create",
            side_effect=Exception("boom"),
        ):
            with pytest.raises(Exception, match="boom"):
                create_organization(owner=user_a, name="Acme")

        assert Organization.objects.filter(name="Acme").count() == 0

    def test_two_orgs_with_same_name_get_distinct_slugs(self, user_a, user_b):
        """
        Assumes slug uniqueness is handled (either in the model's save()
        or a service helper) — this just proves the outward behavior:
        creating two orgs with the same name doesn't crash.
        """
        org1 = create_organization(owner=user_a, name="Acme")
        org2 = create_organization(owner=user_b, name="Acme")
        assert org1.slug != org2.slug


# ---------------------------------------------------------------------------
# update_organization
# ---------------------------------------------------------------------------

class TestUpdateOrganization:
    def test_owner_can_update_name(self, user_a, org_a, membership_a):
        updated = update_organization(actor=user_a, organization=org_a, name="New Name")
        assert updated.name == "New Name"
        org_a.refresh_from_db()
        assert org_a.name == "New Name"

    def test_admin_can_update_name(self, org_a):
        admin_user = UserFactory()
        MembershipFactory(organization=org_a, user=admin_user, role=MemberShip.Role.ADMIN)

        updated = update_organization(actor=admin_user, organization=org_a, name="New Name")
        assert updated.name == "New Name"

    def test_manager_cannot_update_name(self, org_a):
        manager_user = UserFactory()
        MembershipFactory(organization=org_a, user=manager_user, role=MemberShip.Role.MANAGER)

        with pytest.raises(InsufficientRoleError):
            update_organization(actor=manager_user, organization=org_a, name="New Name")

    def test_member_cannot_update_name(self, org_a):
        member_user = UserFactory()
        MembershipFactory(organization=org_a, user=member_user, role=MemberShip.Role.MEMBER)

        with pytest.raises(InsufficientRoleError):
            update_organization(actor=member_user, organization=org_a, name="New Name")

    def test_non_member_cannot_update(self, user_b, org_a):
        with pytest.raises(NotAMemberError):
            update_organization(actor=user_b, organization=org_a, name="New Name")

    def test_raises_on_disallowed_field(self, user_a, org_a, membership_a):
        with pytest.raises(ValueError):
            update_organization(actor=user_a, organization=org_a, status="SUSPENDED")


# ---------------------------------------------------------------------------
# update_organization_settings
# ---------------------------------------------------------------------------

class TestUpdateOrganizationSettings:
    def test_owner_can_update_settings(self, user_a, org_a, membership_a):
        updated = update_organization_settings(
            actor=user_a, organization=org_a, allow_public_signup=True
        )
        assert updated.allow_public_signup is True

    def test_member_cannot_update_settings(self, org_a):
        member_user = UserFactory()
        MembershipFactory(organization=org_a, user=member_user, role=MemberShip.Role.MEMBER)

        with pytest.raises(InsufficientRoleError):
            update_organization_settings(
                actor=member_user, organization=org_a, allow_public_signup=True
            )

    def test_non_member_cannot_update_settings(self, user_b, org_a):
        with pytest.raises(NotAMemberError):
            update_organization_settings(
                actor=user_b, organization=org_a, allow_public_signup=True
            )

    def test_raises_on_disallowed_field(self, user_a, org_a, membership_a):
        with pytest.raises(ValueError):
            update_organization_settings(actor=user_a, organization=org_a, name="hijack")


# ---------------------------------------------------------------------------
# change_member_role
# ---------------------------------------------------------------------------

class TestChangeMemberRole:
    def test_owner_can_promote_member_to_manager(self, org_a, membership_a, user_a):
        target_user = UserFactory()
        target_membership = MembershipFactory(
            organization=org_a, user=target_user, role=MemberShip.Role.MEMBER
        )

        updated = change_member_role(
            actor=user_a, membership=target_membership, new_role=MemberShip.Role.MANAGER
        )
        assert updated.role == MemberShip.Role.MANAGER

    def test_admin_can_change_manager_to_member(self, org_a):
        admin_user = UserFactory()
        MembershipFactory(organization=org_a, user=admin_user, role=MemberShip.Role.ADMIN)

        target_user = UserFactory()
        target_membership = MembershipFactory(
            organization=org_a, user=target_user, role=MemberShip.Role.MANAGER
        )

        updated = change_member_role(
            actor=admin_user, membership=target_membership, new_role=MemberShip.Role.MEMBER
        )
        assert updated.role == MemberShip.Role.MEMBER

    def test_cannot_grant_owner_role(self, org_a, membership_a, user_a):
        target_user = UserFactory()
        target_membership = MembershipFactory(
            organization=org_a, user=target_user, role=MemberShip.Role.MEMBER
        )

        with pytest.raises(InsufficientRoleError):
            change_member_role(
                actor=user_a, membership=target_membership, new_role=MemberShip.Role.OWNER
            )

    def test_cannot_change_role_of_equal_rank(self, org_a):
        admin_user = UserFactory()
        MembershipFactory(organization=org_a, user=admin_user, role=MemberShip.Role.ADMIN)

        other_admin_user = UserFactory()
        other_admin_membership = MembershipFactory(
            organization=org_a, user=other_admin_user, role=MemberShip.Role.ADMIN
        )

        with pytest.raises(InsufficientRoleError):
            change_member_role(
                actor=admin_user,
                membership=other_admin_membership,
                new_role=MemberShip.Role.MANAGER,
            )

    def test_cannot_change_role_of_higher_rank(self, org_a, membership_a):
        manager_user = UserFactory()
        MembershipFactory(organization=org_a, user=manager_user, role=MemberShip.Role.MANAGER)

        with pytest.raises(InsufficientRoleError):
            change_member_role(
                actor=manager_user, membership=membership_a, new_role=MemberShip.Role.MEMBER
            )

    def test_cannot_promote_to_a_rank_equal_to_actor(self, org_a):
        admin_user = UserFactory()
        MembershipFactory(organization=org_a, user=admin_user, role=MemberShip.Role.ADMIN)

        target_user = UserFactory()
        target_membership = MembershipFactory(
            organization=org_a, user=target_user, role=MemberShip.Role.MEMBER
        )

        with pytest.raises(InsufficientRoleError):
            change_member_role(
                actor=admin_user, membership=target_membership, new_role=MemberShip.Role.ADMIN
            )

    def test_actor_cannot_change_own_role(self, org_a, membership_a, user_a):
        with pytest.raises(CannotActOnSelfError):
            change_member_role(
                actor=user_a, membership=membership_a, new_role=MemberShip.Role.MEMBER
            )

    def test_non_member_cannot_change_role(self, org_a, user_b):
        target_user = UserFactory()
        target_membership = MembershipFactory(
            organization=org_a, user=target_user, role=MemberShip.Role.MEMBER
        )

        with pytest.raises(NotAMemberError):
            change_member_role(
                actor=user_b, membership=target_membership, new_role=MemberShip.Role.MANAGER
            )


# ---------------------------------------------------------------------------
# remove_member
# ---------------------------------------------------------------------------

class TestRemoveMember:
    def test_owner_can_remove_member(self, org_a, membership_a, user_a):
        target_user = UserFactory()
        target_membership = MembershipFactory(
            organization=org_a, user=target_user, role=MemberShip.Role.MEMBER
        )

        remove_member(actor=user_a, membership=target_membership)

        assert not MemberShip.objects.filter(pk=target_membership.pk).exists()

    def test_admin_cannot_remove_owner(self, org_a, membership_a):
        admin_user = UserFactory()
        MembershipFactory(organization=org_a, user=admin_user, role=MemberShip.Role.ADMIN)

        with pytest.raises(InsufficientRoleError):
            remove_member(actor=admin_user, membership=membership_a)

    def test_cannot_remove_equal_rank(self, org_a):
        admin_user = UserFactory()
        MembershipFactory(organization=org_a, user=admin_user, role=MemberShip.Role.ADMIN)

        other_admin_membership = MembershipFactory(
            organization=org_a, user=UserFactory(), role=MemberShip.Role.ADMIN
        )

        with pytest.raises(InsufficientRoleError):
            remove_member(actor=admin_user, membership=other_admin_membership)

    

    def test_can_remove_an_owner_if_another_owner_remains(self, org_a, membership_a, user_a):
        second_owner_user = UserFactory()
        second_owner_membership = MembershipFactory(
            organization=org_a, user=second_owner_user, role=MemberShip.Role.OWNER
        )

        # membership_a (user_a) removes the second owner — one owner
        # (user_a) still remains, so this must succeed.
        remove_member(actor=user_a, membership=second_owner_membership)

        assert not MemberShip.objects.filter(pk=second_owner_membership.pk).exists()
        assert MemberShip.objects.filter(pk=membership_a.pk).exists()

    def test_actor_cannot_remove_self(self, org_a, membership_a, user_a):
        with pytest.raises(CannotActOnSelfError):
            remove_member(actor=user_a, membership=membership_a)

    def test_non_member_cannot_remove(self, org_a, user_b):
        target_membership = MembershipFactory(
            organization=org_a, user=UserFactory(), role=MemberShip.Role.MEMBER
        )

        with pytest.raises(NotAMemberError):
            remove_member(actor=user_b, membership=target_membership)


# ---------------------------------------------------------------------------
# leave_organization
# ---------------------------------------------------------------------------

class TestLeaveOrganization:
    def test_member_can_leave(self, org_a):
        member_user = UserFactory()
        MembershipFactory(organization=org_a, user=member_user, role=MemberShip.Role.MEMBER)

        leave_organization(actor=member_user, organization=org_a)

        assert not MemberShip.objects.filter(
            organization=org_a, user=member_user
        ).exists()

    def test_owner_can_leave_if_another_owner_remains(self, org_a, membership_a, user_a):
        second_owner_user = UserFactory()
        MembershipFactory(organization=org_a, user=second_owner_user, role=MemberShip.Role.OWNER)

        leave_organization(actor=user_a, organization=org_a)

        assert not MemberShip.objects.filter(organization=org_a, user=user_a).exists()

    def test_last_owner_cannot_leave(self, org_a, membership_a, user_a):
        with pytest.raises(CannotRemoveLastOwnerError):
            leave_organization(actor=user_a, organization=org_a)

        # Confirm the membership was NOT deleted despite the raise.
        assert MemberShip.objects.filter(pk=membership_a.pk).exists()

    def test_non_member_cannot_leave(self, org_a, user_b):
        with pytest.raises(NotAMemberError):
            leave_organization(actor=user_b, organization=org_a)