from rest_framework_simplejwt.views import (
    TokenObtainPairView,
    TokenRefreshView,
    TokenBlacklistView,
)
from django.urls import path
from apps.accounts.views import (
    RegisterView,
    VerifyEmailView,
    RequestPasswordResetView,
    ResetPasswordView,
)

app_name = "accounts"

urlpatterns = [
    path("register/", RegisterView.as_view(), name="register"),
    path("token/", TokenObtainPairView.as_view(), name="token_obtain_pair"),
    path("token/refresh/", TokenRefreshView.as_view(), name="token_refresh"),
    path("logout/", TokenBlacklistView.as_view(), name="token_blacklist"),
    path("email/verify/", VerifyEmailView.as_view(), name="verify_email"),
    path(
        "request-password-reset/",
        RequestPasswordResetView.as_view(),
        name="request_password_reset",
    ),
    path(
        "reset-password/<str:token>/",
        ResetPasswordView.as_view(),
        name=" reset_password",
    ),
]
