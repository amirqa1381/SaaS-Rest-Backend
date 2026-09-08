import pytest
from types import SimpleNamespace

from apps.organizations.models import MemberShip
from apps.organizations.permissions import (
    IsOrganizationMember,
    has_role,
    get_active_membership,
    resolve_organization,
)
from common.permissions import IsObjectInUsersOrganization

pytestmark = pytest.mark.django_db


def make_request(user):
    return SimpleNamespace(user=user)


def make_view(org_id):
    return SimpleNamespace(kwargs={"organization_pk": str(org_id)})


class TestGetActiveMembership:
    def test_returns_membership_for_active_member(self, user_a, org_a, membership_a):
        result = get_active_membership(user_a, org_a)
        assert result == membership_a

    def test_returns_none_for_non_member(self, user_b, org_a):
        result = get_active_membership(user_b, org_a)
        assert result is None

    def test_returns_none_for_suspended_membership(self, user_a, org_a, membership_a):
        membership_a.status = MemberShip.Status.SUSPENDED
        membership_a.save()
        result = get_active_membership(user_a, org_a)
        assert result is None

    def test_returns_none_for_unauthenticated_user(self, org_a):
        result = get_active_membership(None, org_a)
        assert result is None


class TestResolveOrganization:
    def test_resolves_from_organization_pk_kwarg(self, org_a):
        view = SimpleNamespace(kwargs={"organization_pk": str(org_a.id)})
        assert resolve_organization(view) == org_a

    def test_returns_none_when_no_org_kwarg(self):
        view = SimpleNamespace(kwargs={})
        assert resolve_organization(view) is None

    def test_returns_none_for_nonexistent_org_id(self):
        import uuid

        view = SimpleNamespace(kwargs={"organization_pk": str(uuid.uuid4())})
        assert resolve_organization(view) is None


class TestIsOrganizationMember:
    permission = IsOrganizationMember()

    def test_allows_active_member(self, user_a, org_a, membership_a):
        request = make_request(user_a)
        view = make_view(org_a.id)

        assert self.permission.has_permission(request, view) is True
        # Confirms the stash-for-downstream behavior works
        assert request.organization == org_a
        assert request.membership == membership_a

    def test_denies_user_from_a_different_org(self, user_b, org_a):
        """
        The core cross-tenant case: user_b (member of org_b only) tries
        to act against org_a via the URL.
        """
        request = make_request(user_b)
        view = make_view(org_a.id)

        assert self.permission.has_permission(request, view) is False

    def test_denies_unauthenticated_user(self, org_a):
        request = SimpleNamespace(user=SimpleNamespace(is_authenticated=False))
        view = make_view(org_a.id)

        assert self.permission.has_permission(request, view) is False

    def test_denies_suspended_membership(self, user_a, org_a, membership_a):
        membership_a.status = MemberShip.Status.SUSPENDED
        membership_a.save()
        request = make_request(user_a)
        view = make_view(org_a.id)

        assert self.permission.has_permission(request, view) is False

    def test_denies_when_org_id_missing_from_url(self, user_a):
        request = make_request(user_a)
        view = SimpleNamespace(kwargs={})

        assert self.permission.has_permission(request, view) is False


class TestHasRole:
    def test_allows_role_at_minimum(self, user_a, org_a, membership_a):
        # membership_a fixture is OWNER
        request = make_request(user_a)
        request.membership = membership_a
        view = make_view(org_a.id)

        permission = has_role(MemberShip.Role.OWNER)()
        assert permission.has_permission(request, view) is True

    def test_allows_role_above_minimum(self, user_a, org_a, membership_a):
        request = make_request(user_a)
        request.membership = membership_a  # OWNER
        view = make_view(org_a.id)

        permission = has_role(MemberShip.Role.MEMBER)()
        assert permission.has_permission(request, view) is True

    def test_denies_role_below_minimum(self, user_a, org_a, membership_a):
        membership_a.role = MemberShip.Role.MEMBER
        membership_a.save()
        request = make_request(user_a)
        request.membership = membership_a
        view = make_view(org_a.id)

        permission = has_role(MemberShip.Role.ADMIN)()
        assert permission.has_permission(request, view) is False

    def test_denies_when_membership_not_attached(self, user_a, org_a):
        """
        Simulates IsOrganizationMember not having run first — fail closed,
        don't assume.
        """
        request = make_request(user_a)
        view = make_view(org_a.id)

        permission = has_role(MemberShip.Role.MEMBER)()
        assert permission.has_permission(request, view) is False


class TestIsObjectInUsersOrganization:
    permission = IsObjectInUsersOrganization()

    def test_allows_object_in_users_org(self, org_a):
        request = SimpleNamespace(organization=org_a)
        fake_obj = SimpleNamespace(organization_id=org_a.id)

        assert self.permission.has_object_permission(request, None, fake_obj) is True

    def test_denies_object_in_different_org(self, org_a, org_b):
        """
        The exact scenario this class exists for: object belongs to
        org_b, but the request is scoped to org_a.
        """
        request = SimpleNamespace(organization=org_a)
        fake_obj = SimpleNamespace(organization_id=org_b.id)

        assert self.permission.has_object_permission(request, None, fake_obj) is False

    def test_denies_when_request_has_no_organization(self, org_a):
        request = SimpleNamespace(organization=None)
        fake_obj = SimpleNamespace(organization_id=org_a.id)

        assert self.permission.has_object_permission(request, None, fake_obj) is False

    def test_fails_closed_on_object_without_organization_id(self, org_a):
        request = SimpleNamespace(organization=org_a)
        fake_obj = SimpleNamespace()  # no organization_id at all

        assert self.permission.has_object_permission(request, None, fake_obj) is False