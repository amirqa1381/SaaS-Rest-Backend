import pytest
from django.urls import reverse

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
