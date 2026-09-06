from datetime import timedelta
from unittest.mock import patch
import pytest
from django.utils import timezone
from rest_framework import status

from apps.accounts.models import EmailVerificationToken
from apps.accounts.services import (
    InvalidOrExpiredTokenError,
    _hash_token,
    issue_email_verification_token,
    verify_email_token,
)


@pytest.mark.django_db
class TestEmailVerificationService:

    def test_issue_email_verification_token_creates_record(self, existing_user):
        raw_token = issue_email_verification_token(existing_user)

        assert raw_token is not None
        assert EmailVerificationToken.objects.filter(user=existing_user).exists()
        token_obj = EmailVerificationToken.objects.get(user=existing_user)
        assert token_obj.token_hash == _hash_token(raw_token)
        assert token_obj.is_valid is True

    def test_verify_email_token_success(self, existing_user):
        assert existing_user.is_email_verified is False
        raw_token = issue_email_verification_token(existing_user)

        verified_user = verify_email_token(token=raw_token)
        verified_user.refresh_from_db()

        assert verified_user.pk == existing_user.pk
        assert verified_user.is_email_verified is True

        token_obj = EmailVerificationToken.objects.get(token_hash=_hash_token(raw_token))
        assert token_obj.is_used is True

    def test_verify_email_invalid_token_raises_error(self):
        with pytest.raises(InvalidOrExpiredTokenError, match="invalid"):
            verify_email_token(token="invalid_raw_token")

    def test_verify_email_expired_token_raises_error(self, existing_user):
        raw_token = "expired_raw_token_value"
        EmailVerificationToken.objects.create(
            user=existing_user,
            token_hash=_hash_token(raw_token),
            expires_at=timezone.now() - timedelta(minutes=5),
        )

        with pytest.raises(InvalidOrExpiredTokenError, match="expired or already used"):
            verify_email_token(token=raw_token)

    def test_verify_email_already_used_token_raises_error(self, existing_user):
        raw_token = issue_email_verification_token(existing_user)
        verify_email_token(token=raw_token)

        with pytest.raises(InvalidOrExpiredTokenError, match="expired or already used"):
            verify_email_token(token=raw_token)


@pytest.mark.django_db
class TestEmailVerificationView:

    def test_verify_email_endpoint_success(self, api_client, email_verification_token, verify_email_url):
        raw_token, user = email_verification_token

        response = api_client.post(verify_email_url, {"token": raw_token}, format="json")

        assert response.status_code == status.HTTP_200_OK
        assert response.data["detail"] == "Email verified successfully."
        user.refresh_from_db()
        assert user.is_email_verified is True

    def test_verify_email_endpoint_with_invalid_token(self, api_client, verify_email_url):
        response = api_client.post(verify_email_url, {"token": "random_fake_token"}, format="json")

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert "detail" in response.data

    def test_verify_email_endpoint_missing_token(self, api_client, verify_email_url):
        response = api_client.post(verify_email_url, {}, format="json")

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert "token" in response.data