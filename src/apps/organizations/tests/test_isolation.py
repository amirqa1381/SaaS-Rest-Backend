import pytest
from django.urls import reverse

from .factories import OrganizationInvitationFactory
from apps.organizations.models import OrganizationInvitation

pytestmark = pytest.mark.django_db


class TestOrganizationIsolation:
    """
    Cross-org access attempts against the Organization detail endpoint.
    Will fail until apps/organizations/urls.py + views exist — that's
    the point: this is the contract the views must satisfy.
    """

    def test_user_cannot_view_another_orgs_detail(self, authed_client_b, org_a):
        url = reverse("organizations:organization-detail", kwargs={"pk": org_a.id})
        response = authed_client_b.get(url)
        assert response.status_code in (403, 404)

    def test_user_cannot_update_another_orgs_detail(self, authed_client_b, org_a):
        url = reverse("organizations:organization-detail", kwargs={"pk": org_a.id})
        response = authed_client_b.patch(url, {"name": "Hijacked"}, format="json")
        assert response.status_code in (403, 404)

    def test_member_of_org_can_view_own_org(self, authed_client_a, org_a):
        url = reverse("organizations:organization-detail", kwargs={"pk": org_a.id})
        response = authed_client_a.get(url)
        assert response.status_code == 200


class TestMembershipIsolation:
    def test_user_cannot_list_another_orgs_members(self, authed_client_b, org_a):
        url = reverse(
            "organizations:membership-list", kwargs={"organization_pk": org_a.id}
        )
        response = authed_client_b.get(url)
        assert response.status_code in (403, 404)

    def test_user_cannot_change_role_in_another_org(
        self, authed_client_b, org_a, membership_a
    ):
        url = reverse(
            "organizations:membership-detail",
            kwargs={"organization_pk": org_a.id, "pk": membership_a.id},
        )
        response = authed_client_b.patch(url, {"role": "ADMIN"}, format="json")
        assert response.status_code in (403, 404)

    def test_member_can_view_own_orgs_membership_list(self, authed_client_a, org_a):
        url = reverse(
            "organizations:membership-list", kwargs={"organization_pk": org_a.id}
        )
        response = authed_client_a.get(url)
        assert response.status_code == 200


class TestOrganizationSettingsIsolation:
    def test_user_cannot_view_another_orgs_settings(self, authed_client_b, org_a):
        url = reverse(
            "organizations:organization-settings", kwargs={"organization_pk": org_a.id}
        )
        response = authed_client_b.get(url)
        assert response.status_code in (403, 404)

    def test_user_cannot_update_another_orgs_settings(self, authed_client_b, org_a):
        url = reverse(
            "organizations:organization-settings", kwargs={"organization_pk": org_a.id}
        )
        response = authed_client_b.patch(
            url, {"allow_public_signup": True}, format="json"
        )
        assert response.status_code in (403, 404)


class TestCrossTenantViaQueryParams:
    """
    Per §15: isolation must hold even via query-string filters, not just
    path params. Once the Project/Task apps exist and support
    ?organization={id} filtering, this pattern gets reused there.
    Placeholder here for the org-scoped list endpoint itself.
    """

    def test_organization_list_only_returns_callers_orgs(
        self, authed_client_a, org_a, org_b
    ):
        url = reverse("organizations:organization-list")
        response = authed_client_a.get(url)
        assert response.status_code == 200
        returned_ids = (
            {item["id"] for item in response.data["results"]}
            if "results" in response.data
            else {item["id"] for item in response.data}
        )
        assert str(org_a.id) in returned_ids
        assert str(org_b.id) not in returned_ids


class TestInvitationIsolation:
    def test_cannot_list_other_orgs_invitations(self, authed_client_a, org_b):
        OrganizationInvitationFactory(organization=org_b)
        url = reverse("organizations:invitation-list-create", kwargs={"organization_pk": org_b.id})
        response = authed_client_a.get(url)
        assert response.status_code in (403, 404)

    def test_cannot_create_invitation_in_other_org(self, authed_client_a, org_b):
        url = reverse("organizations:invitation-list-create", kwargs={"organization_pk": org_b.id})
        response = authed_client_a.post(url, {"email": "x@example.com", "role": "MEMBER"})
        assert response.status_code in (403, 404)

    def test_cannot_revoke_other_orgs_invitation(self, authed_client_a, org_b):
        invitation = OrganizationInvitationFactory(organization=org_b, status=OrganizationInvitation.Status.PENDING)
        url = reverse(
            "organizations:invitation-revoke",
            kwargs={"organization_pk": org_b.id, "invitation_pk": invitation.id},
        )
        response = authed_client_a.post(url)
        assert response.status_code in (403, 404)
        invitation.refresh_from_db()
        assert invitation.status == OrganizationInvitation.Status.PENDING  # untouched

    def test_cannot_revoke_own_orgs_invitation_via_wrong_org_id_in_url(self, authed_client_a, org_a, org_b):
        """Invitation belongs to org_a, but URL claims org_b — should not resolve."""
        invitation = OrganizationInvitationFactory(organization=org_a, status=OrganizationInvitation.Status.PENDING)
        url = reverse(
            "organizations:invitation-revoke",
            kwargs={"organization_pk": org_b.id, "invitation_pk": invitation.id},
        )
        response = authed_client_a.post(url)
        assert response.status_code == 403