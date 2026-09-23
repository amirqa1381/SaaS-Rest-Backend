import pytest
from django.urls import reverse
from rest_framework import status

from .factories import OrganizationInvitationFactory
from apps.organizations.models import OrganizationInvitation
from apps.organizations.services import _hash_token

pytestmark = pytest.mark.django_db


class TestInvitationListCreateView:
    def test_owner_can_create_invitation(self, authed_client_a, org_a):
        url = reverse("organizations:invitation-list-create", kwargs={"organization_pk": org_a.id})
        response = authed_client_a.post(url, {"email": "new@example.com", "role": "MEMBER"})
        assert response.status_code == status.HTTP_201_CREATED
        assert response.data["email"] == "new@example.com"
        assert "token_hash" not in response.data  # never leaked

    def test_invalid_role_rejected(self, authed_client_a, org_a):
        url = reverse("organizations:invitation-list-create", kwargs={"organization_pk": org_a.id})
        response = authed_client_a.post(url, {"email": "new@example.com", "role": "OWNER"})
        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_malformed_email_rejected(self, authed_client_a, org_a):
        url = reverse("organizations:invitation-list-create", kwargs={"organization_pk": org_a.id})
        response = authed_client_a.post(url, {"email": "not-an-email", "role": "MEMBER"})
        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_list_invitations(self, authed_client_a, org_a):
        OrganizationInvitationFactory(organization=org_a)
        OrganizationInvitationFactory(organization=org_a)
        url = reverse("organizations:invitation-list-create", kwargs={"organization_pk": org_a.id})
        response = authed_client_a.get(url)
        assert response.status_code == status.HTTP_200_OK
        assert len(response.data) == 2

    def test_unauthenticated_rejected(self, api_client, org_a):
        url = reverse("organizations:invitation-list-create", kwargs={"organization_pk": org_a.id})
        response = api_client.post(url, {"email": "x@example.com", "role": "MEMBER"})
        assert response.status_code == status.HTTP_401_UNAUTHORIZED


class TestInvitationRevokeView:
    def test_owner_can_revoke(self, authed_client_a, org_a):
        invitation = OrganizationInvitationFactory(organization=org_a, status=OrganizationInvitation.Status.PENDING)
        url = reverse(
            "organizations:invitation-revoke",
            kwargs={"organization_pk": org_a.id, "invitation_pk": invitation.id},
        )
        response = authed_client_a.post(url)
        assert response.status_code == status.HTTP_204_NO_CONTENT
        invitation.refresh_from_db()
        assert invitation.status == OrganizationInvitation.Status.REVOKED

    def test_revoke_nonexistent_invitation_404s(self, authed_client_a, org_a):
        url = reverse(
            "organizations:invitation-revoke",
            kwargs={"organization_pk": org_a.id, "invitation_pk": "00000000-0000-0000-0000-000000000000"},
        )
        response = authed_client_a.post(url)
        assert response.status_code == status.HTTP_404_NOT_FOUND

    def test_revoke_already_accepted_returns_400(self, authed_client_a, org_a):
        invitation = OrganizationInvitationFactory(organization=org_a, status=OrganizationInvitation.Status.ACCEPTED)
        url = reverse(
            "organizations:invitation-revoke",
            kwargs={"organization_pk": org_a.id, "invitation_pk": invitation.id},
        )
        response = authed_client_a.post(url)
        assert response.status_code == status.HTTP_400_BAD_REQUEST


class TestInvitationAcceptView:
    def test_accept_valid_invitation(self, authed_client_b, org_a, user_b):
        raw_token = "view-test-token"
        invitation = OrganizationInvitationFactory(
            organization=org_a,
            email=user_b.email,
            token_hash=_hash_token(raw_token),
            status=OrganizationInvitation.Status.PENDING,
        )
        url = reverse("organizations:invitation-accept")
        response = authed_client_b.post(url, {"token": raw_token})
        assert response.status_code == status.HTTP_200_OK
        assert response.data["organization"] == str(org_a.id)

    def test_accept_invalid_token_returns_400(self, authed_client_b):
        url = reverse("organizations:invitation-accept")
        response = authed_client_b.post(url, {"token": "garbage"})
        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_accept_missing_token_returns_400(self, authed_client_b):
        url = reverse("organizations:invitation-accept")
        response = authed_client_b.post(url, {})
        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_accept_requires_authentication(self, api_client):
        url = reverse("organizations:invitation-accept")
        response = api_client.post(url, {"token": "whatever"})
        assert response.status_code == status.HTTP_401_UNAUTHORIZED