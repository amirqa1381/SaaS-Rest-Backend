import pytest
from django.apps import apps as django_apps

pytestmark = pytest.mark.django_db

BLACKLIST_APP_INSTALLED = django_apps.is_installed(
    "rest_framework_simplejwt.token_blacklist"
)


class TestTokenObtainPairView:
    def test_login_with_valid_credentials_returns_tokens(
        self, api_client, token_obtain_url, existing_user
    ):
        response = api_client.post(
            token_obtain_url,
            {"email": existing_user.email, "password": "S0meStr0ngP@ssword!"},
            format="json",
        )

        assert response.status_code == 200
        assert "access" in response.data
        assert "refresh" in response.data

    def test_login_with_wrong_password_returns_401(
        self, api_client, token_obtain_url, existing_user
    ):
        response = api_client.post(
            token_obtain_url,
            {"email": existing_user.email, "password": "WrongPassword123!"},
            format="json",
        )

        assert response.status_code == 401

    def test_login_with_unknown_email_returns_401(self, api_client, token_obtain_url):
        response = api_client.post(
            token_obtain_url,
            {"email": "nobody@example.com", "password": "S0meStr0ngP@ssword!"},
            format="json",
        )

        assert response.status_code == 401

    def test_login_for_inactive_user_returns_401(
        self, api_client, token_obtain_url, existing_user
    ):
        existing_user.is_active = False
        existing_user.save(update_fields=["is_active"])

        response = api_client.post(
            token_obtain_url,
            {"email": existing_user.email, "password": "S0meStr0ngP@ssword!"},
            format="json",
        )

        assert response.status_code == 401

    def test_login_missing_credentials_returns_400(self, api_client, token_obtain_url):
        response = api_client.post(token_obtain_url, {}, format="json")

        assert response.status_code == 400


class TestTokenRefreshView:
    def _login(self, api_client, token_obtain_url, existing_user):
        response = api_client.post(
            token_obtain_url,
            {"email": existing_user.email, "password": "S0meStr0ngP@ssword!"},
            format="json",
        )
        return response.data["refresh"]

    def test_refresh_with_valid_token_returns_new_access_token(
        self, api_client, token_obtain_url, token_refresh_url, existing_user
    ):
        refresh_token = self._login(api_client, token_obtain_url, existing_user)

        response = api_client.post(
            token_refresh_url, {"refresh": refresh_token}, format="json"
        )

        assert response.status_code == 200
        assert "access" in response.data

    def test_refresh_with_invalid_token_returns_401(
        self, api_client, token_refresh_url
    ):
        response = api_client.post(
            token_refresh_url, {"refresh": "not-a-real-token"}, format="json"
        )

        assert response.status_code == 401

    def test_refresh_missing_token_returns_400(self, api_client, token_refresh_url):
        response = api_client.post(token_refresh_url, {}, format="json")

        assert response.status_code == 400


class TestTokenBlacklistView:
    def _login(self, api_client, token_obtain_url, existing_user):
        response = api_client.post(
            token_obtain_url,
            {"email": existing_user.email, "password": "S0meStr0ngP@ssword!"},
            format="json",
        )
        return response.data["refresh"]

    def test_logout_missing_token_returns_400(self, api_client, token_blacklist_url):
        # Doesn't require the token_blacklist app/table — fails validation
        # before any DB write is attempted.
        response = api_client.post(token_blacklist_url, {}, format="json")

        assert response.status_code == 400

    def test_logout_with_garbage_token_returns_401(
        self, api_client, token_blacklist_url
    ):
        response = api_client.post(
            token_blacklist_url, {"refresh": "not-a-real-token"}, format="json"
        )

        assert response.status_code == 401

    @pytest.mark.skipif(
        not BLACKLIST_APP_INSTALLED,
        reason="rest_framework_simplejwt.token_blacklist is not in INSTALLED_APPS",
    )
    def test_logout_blacklists_the_refresh_token(
        self,
        api_client,
        token_obtain_url,
        token_refresh_url,
        token_blacklist_url,
        existing_user,
    ):
        refresh_token = self._login(api_client, token_obtain_url, existing_user)

        logout_response = api_client.post(
            token_blacklist_url, {"refresh": refresh_token}, format="json"
        )
        assert logout_response.status_code == 200

        # The now-blacklisted refresh token can no longer mint new access tokens.
        reuse_response = api_client.post(
            token_refresh_url, {"refresh": refresh_token}, format="json"
        )
        assert reuse_response.status_code == 401
