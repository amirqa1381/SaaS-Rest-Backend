from django.urls import reverse, resolve
from apps.accounts.views import RegisterView


class TestAccountsUrls:
    """Guards against silent routing breakage: a renamed URL, a dropped
    `app_name` namespace, or a view swapped out from under a `path()` entry
    would previously go unnoticed because the view tests called
    `RegisterView.as_view()` directly instead of going through `reverse()`.
    """

    def test_register_url_resolves_to_register_view(self):
        url = reverse("accounts:register")
        assert url.endswith("/register/")
        assert resolve(url).func.view_class == RegisterView

    def test_token_obtain_pair_url_resolves_by_name(self):
        url = reverse("accounts:token_obtain_pair")

        assert url.endswith("/token/")


    def test_token_refresh_url_resolves_by_name(self):
        url = reverse("accounts:token_refresh")

        assert url.endswith("/token/refresh/")

    def test_token_blacklist_url_resolves_by_name(self):
        url = reverse("accounts:token_blacklist")

        assert url.endswith("/logout/")

    def test_all_expected_url_names_are_registered(self):
        for name in ["register", "token_obtain_pair", "token_refresh", "token_blacklist"]:
            url = reverse(f"accounts:{name}")
            assert url is not None