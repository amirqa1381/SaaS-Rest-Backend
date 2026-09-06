from datetime import timedelta
from unittest.mock import patch
import pytest
from django.utils import timezone
from rest_framework import status

from apps.accounts.models import PasswordResetToken, User
from apps.accounts.services import (
    InvalidOrExpiredTokenError,
    _hash_token,
    request_password_reset,
    reset_password,
)


@pytest.mark.django_db
class TestPasswordResetService:

    @patch("apps.accounts.services.send_password_reset_email.delay_on_commit")
    def test_request_password_reset_active_user_creates_token_and_queues_email(
        self, mock_send_email, existing_user
    ):
        raw_token = request_password_reset(email=existing_user.email)

        assert raw_token is not None
        assert PasswordResetToken.objects.filter(user=existing_user).exists()
        token_obj = PasswordResetToken.objects.get(user=existing_user)
        assert token_obj.token_hash == _hash_token(raw_token)
        mock_send_email.assert_called_once()

    @patch("apps.accounts.services.send_password_reset_email.delay_on_commit")
    def test_request_password_reset_nonexistent_email_returns_none(self, mock_send_email):
        raw_token = request_password_reset(email="nonexistent@example.com")

        assert raw_token is None
        mock_send_email.assert_not_called()

    @patch("apps.accounts.services.send_password_reset_email.delay_on_commit")
    def test_request_password_reset_inactive_user_returns_none(self, mock_send_email):
        inactive_user = User.objects.create_user(
            email="inactive@example.com",
            password="S0meStr0ngP@ssword!",
            is_active=False,
        )

        raw_token = request_password_reset(email=inactive_user.email)

        assert raw_token is None
        mock_send_email.assert_not_called()

    def test_reset_password_success(self, existing_user, password_reset_token):
        raw_token, _ = password_reset_token
        new_password = "BrandN3wSecurePassword!"

        user = reset_password(token=raw_token, new_password=new_password)
        user.refresh_from_db()

        assert user.check_password(new_password) is True
        token_obj = PasswordResetToken.objects.get(token_hash=_hash_token(raw_token))
        assert token_obj.is_used is True

    def test_reset_password_invalidates_all_other_tokens(self, existing_user, password_reset_token):
        raw_token, _ = password_reset_token

        # Create another reset token for the same user
        other_token = PasswordResetToken.objects.create(
            user=existing_user,
            token_hash=_hash_token("another-token-value"),
            expires_at=timezone.now() + timedelta(hours=1),
        )

        reset_password(token=raw_token, new_password="NewValidPassword123!")

        other_token.refresh_from_db()
        assert other_token.is_used is True

    def test_reset_password_invalid_token_raises_error(self):
        with pytest.raises(InvalidOrExpiredTokenError, match="invalid"):
            reset_password(token="nonexistent-token", new_password="NewValidPassword123!")

    def test_reset_password_expired_token_raises_error(self, existing_user):
        raw_token = "expired-token-raw"
        PasswordResetToken.objects.create(
            user=existing_user,
            token_hash=_hash_token(raw_token),
            expires_at=timezone.now() - timedelta(minutes=10),
        )

        with pytest.raises(InvalidOrExpiredTokenError, match="expired or already used"):
            reset_password(token=raw_token, new_password="NewValidPassword123!")


@pytest.mark.django_db
class TestRequestPasswordResetView:

    @patch("apps.accounts.services.send_password_reset_email.delay_on_commit")
    def test_request_reset_existing_email_returns_200(
        self, mock_email, api_client, existing_user, request_password_reset_url
    ):
        response = api_client.post(
            request_password_reset_url,
            {"email": existing_user.email},
            format="json",
        )

        assert response.status_code == status.HTTP_200_OK
        assert response.data["detail"] == "Password reset link sent if the email exists."
        mock_email.assert_called_once()

    @patch("apps.accounts.services.send_password_reset_email.delay_on_commit")
    def test_request_reset_nonexistent_email_returns_200_enumeration_protection(
        self, mock_email, api_client, request_password_reset_url
    ):
        response = api_client.post(
            request_password_reset_url,
            {"email": "notfound@example.com"},
            format="json",
        )

        assert response.status_code == status.HTTP_200_OK
        assert response.data["detail"] == "Password reset link sent if the email exists."
        mock_email.assert_not_called()

    def test_request_reset_invalid_email_format_returns_400(
        self, api_client, request_password_reset_url
    ):
        response = api_client.post(
            request_password_reset_url,
            {"email": "invalid-email-format"},
            format="json",
        )

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert "email" in response.data