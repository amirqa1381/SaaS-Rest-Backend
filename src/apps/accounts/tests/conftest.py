import pytest
from datetime import timedelta
from django.utils import timezone
from django.urls import reverse
from rest_framework.test import APIClient, APIRequestFactory

from apps.accounts.models import User, EmailVerificationToken, PasswordResetToken
from apps.accounts.services import _hash_token, issue_email_verification_token


@pytest.fixture
def api_rf():
    """Bare DRF request factory — kept for any test that wants to call a
    view directly, bypassing routing."""
    return APIRequestFactory()


@pytest.fixture
def api_client():
    """A real client that goes through URL routing/namespacing, so a wrong
    `reverse()` name or missing route fails the test instead of being
    silently skipped."""
    return APIClient()


@pytest.fixture
def valid_user_payload():
    return {
        "email": "Jane.Doe@Example.com",
        "password": "S0meStr0ngP@ssword!",
        "first_name": "Jane",
        "last_name": "Doe",
    }


@pytest.fixture
def register_url():
    # Resolved lazily inside a fixture (not at import/class-body time) so
    # Django's URL resolver is guaranteed to be fully configured.
    return reverse("accounts:register")


@pytest.fixture
def token_obtain_url():
    return reverse("accounts:token_obtain_pair")


@pytest.fixture
def token_refresh_url():
    return reverse("accounts:token_refresh")


@pytest.fixture
def token_blacklist_url():
    return reverse("accounts:token_blacklist")


@pytest.fixture
def existing_user(db):
    """A user already persisted with a known raw password, for login/token
    tests that need to authenticate against real credentials."""
    return User.objects.create_user(
        email="existing@example.com",
        password="S0meStr0ngP@ssword!",
        first_name="Existing",
        last_name="User",
    )


@pytest.fixture
def verify_email_url():
    return reverse("accounts:verify_email")


@pytest.fixture
def request_password_reset_url():
    return reverse("accounts:request_password_reset")


@pytest.fixture
def email_verification_token(existing_user):
    raw_token = issue_email_verification_token(existing_user)
    return raw_token, existing_user


@pytest.fixture
def password_reset_token(existing_user):
    raw_token = "valid-raw-reset-token-123456789"
    token_hash = _hash_token(raw_token)
    token_obj = PasswordResetToken.objects.create(
        user=existing_user,
        token_hash=token_hash,
        expires_at=timezone.now() + timedelta(hours=1),
    )
    return raw_token, token_obj