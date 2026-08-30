import pytest

from apps.accounts.models import User

pytestmark = pytest.mark.django_db


class TestRegisterView:
    """Goes through real URL routing (`reverse("accounts:register")` +
    `APIClient`) rather than calling `RegisterView.as_view()` directly, so
    a broken route/namespace fails these tests instead of going unnoticed.
    """

    def test_register_success_returns_201_with_user_data(
        self, api_client, register_url, valid_user_payload
    ):
        response = api_client.post(register_url, data=valid_user_payload, format="json")
        assert response.status_code == 201
        assert response.data["email"] == valid_user_payload["email"].lower()
        assert response.data["first_name"] == valid_user_payload["first_name"]

    def test_register_response_never_includes_password(
        self, api_client, register_url, valid_user_payload
    ):
        response = api_client.post(register_url, valid_user_payload, format="json")

        assert "password" not in response.data

    def test_register_creates_user_in_db(
        self, api_client, register_url, valid_user_payload
    ):
        api_client.post(register_url, valid_user_payload, format="json")
        assert User.objects.filter(email=valid_user_payload["email"].lower()).exists()

    def test_register_with_existing_email_returns_400(
        self, api_client, register_url, valid_user_payload
    ):
        # Create a user with the same email first
        User.objects.create_user(**valid_user_payload)

        response = api_client.post(register_url, valid_user_payload, format="json")
        assert response.status_code == 400
        assert "email" in response.data
        assert (
            User.objects.filter(email=valid_user_payload["email"].lower()).count() == 1
        )

    def test_register_duplicate_email_different_case_returns_400(
        self, api_client, register_url, valid_user_payload
    ):
        api_client.post(register_url, valid_user_payload, format="json")

        payload = dict(valid_user_payload)
        payload["email"] = payload["email"].upper()
        response = api_client.post(register_url, payload, format="json")

        assert response.status_code == 400
        assert "email" in response.data

    def test_register_with_invalid_email_returns_400(
        self, api_client, register_url, valid_user_payload
    ):
        response = api_client.post(
            register_url,
            {**valid_user_payload, "email": "invalid-email"},
            format="json",
        )

        assert response.status_code == 400
        assert "email" in response.data

    def test_register_with_weak_password_returns_400(
        self, api_client, register_url, valid_user_payload
    ):
        response = api_client.post(
            register_url, {**valid_user_payload, "password": "123"}, format="json"
        )

        assert response.status_code == 400
        assert "password" in response.data

    def test_register_with_missing_fields_returns_400(
        self, api_client, register_url, valid_user_payload
    ):
        response = api_client.post(register_url, {}, format="json")

        assert response.status_code == 400
        assert "email" in response.data
        assert "password" in response.data

    def test_register_only_accepts_post_method(
        self, api_client, register_url, valid_user_payload
    ):
        response = api_client.get(register_url)
        assert response.status_code == 405  # Method Not Allowed
