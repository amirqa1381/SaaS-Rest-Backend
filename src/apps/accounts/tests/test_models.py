import pytest
from django.db import IntegrityError, transaction

from apps.accounts.models import User

pytestmark = pytest.mark.django_db


class TestUserModel:
    def test_create_user_sets_expected_defaults(self):
        user = User.objects.create_user(email="test@example.com", password="pass12345")

        assert user.email == "test@example.com"
        assert user.is_active is True
        assert user.is_staff is False
        assert user.is_email_verified is False
        assert user.check_password("pass12345")

    def test_str_returns_email(self):
        user = User.objects.create_user(email="str@example.com", password="pass12345")

        assert str(user) == "str@example.com"

    def test_email_must_be_unique(self):
        User.objects.create_user(email="dup@example.com", password="pass12345")

        with pytest.raises(IntegrityError):
            with transaction.atomic():
                User.objects.create_user(email="dup@example.com", password="pass12345")

    def test_username_field_is_email_with_no_required_fields(self):
        assert User.USERNAME_FIELD == "email"
        assert User.REQUIRED_FIELDS == []

    def test_first_and_last_name_default_to_blank(self):
        user = User.objects.create_user(email="blank@example.com", password="pass12345")

        assert user.first_name == ""
        assert user.last_name == ""

    def test_has_uuid_pk_and_timestamps_from_base_model(self):
        user = User.objects.create_user(email="uuid@example.com", password="pass12345")

        assert user.id is not None
        assert user.created_at is not None
        assert user.updated_at is not None

    def test_password_is_stored_hashed_not_plaintext(self):
        user = User.objects.create_user(email="hash@example.com", password="pass12345")

        assert user.password != "pass12345"
        assert user.password.startswith("pbkdf2_") or "$" in user.password