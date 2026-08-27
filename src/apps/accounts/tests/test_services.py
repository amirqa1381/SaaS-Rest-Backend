import pytest

from apps.accounts.models import User
from apps.accounts.services import EmailAlreadyRegisteredError, register_user

pytestmark = pytest.mark.django_db


class TestRegisterUser:
    def test_creates_user_with_hashed_password(self):
        user = register_user(email="new@example.com", password="S0meStr0ngP@ssword!")

        assert user.pk is not None
        assert user.password != "S0meStr0ngP@ssword!"
        assert user.check_password("S0meStr0ngP@ssword!")

    def test_normalizes_email_case_and_whitespace(self):
        user = register_user(
            email="  Mixed.Case@Example.com  ", password="S0meStr0ngP@ssword!"
        )

        assert user.email == "mixed.case@example.com"

    def test_strips_first_and_last_name(self):
        user = register_user(
            email="strip@example.com",
            password="S0meStr0ngP@ssword!",
            first_name="  Jane ",
            last_name=" Doe  ",
        )

        assert user.first_name == "Jane"
        assert user.last_name == "Doe"

    def test_first_and_last_name_default_to_empty(self):
        user = register_user(email="noname@example.com", password="S0meStr0ngP@ssword!")

        assert user.first_name == ""
        assert user.last_name == ""

    def test_duplicate_email_raises_domain_error(self):
        register_user(email="dupe@example.com", password="S0meStr0ngP@ssword!")

        with pytest.raises(EmailAlreadyRegisteredError):
            register_user(email="dupe@example.com", password="An0therStr0ngP@ss!")

    def test_duplicate_email_different_case_raises(self):
        register_user(email="case@example.com", password="S0meStr0ngP@ssword!")

        with pytest.raises(EmailAlreadyRegisteredError):
            register_user(email="CASE@Example.com", password="An0therStr0ngP@ss!")

    def test_failed_registration_does_not_leave_duplicate_or_partial_rows(self):
        register_user(email="atomic@example.com", password="S0meStr0ngP@ssword!")

        with pytest.raises(EmailAlreadyRegisteredError):
            register_user(email="atomic@example.com", password="An0therStr0ngP@ss!")

        assert User.objects.filter(email="atomic@example.com").count() == 1

    def test_returns_a_persisted_user_instance(self):
        user = register_user(email="persisted@example.com", password="S0meStr0ngP@ssword!")

        assert User.objects.filter(pk=user.pk).exists()