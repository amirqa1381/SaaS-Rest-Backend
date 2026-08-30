from rest_framework import status
from django.core.exceptions import ValidationError
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.permissions import AllowAny
from apps.accounts.serializers import (
    RegisterSerializer,
    UserSerializer,
    RequestPasswordResetSerializer,
    ResetPasswordSerializer,
    VerifyEmailSerializer,
)
from apps.accounts.services import (
    register_user,
    EmailAlreadyRegisteredError,
    reset_password,
    verify_email_token,
    InvalidOrExpiredTokenError,
    request_password_reset,
)


class RegisterView(APIView):
    """
    API endpoint for user registration.
    """

    permission_classes = [AllowAny]

    def post(self, request):
        serializer = RegisterSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            user = register_user(**serializer.validated_data)
        except EmailAlreadyRegisteredError as e:
            return Response(
                {"email": ["A user with this email already exists."]},
                status=status.HTTP_400_BAD_REQUEST,
            )
        return Response(UserSerializer(user).data, status=status.HTTP_201_CREATED)


class VerifyEmailView(APIView):
    """
    API endpoint for email verification.
    Expects the raw token in the request body (frontend extracts it
    from the verification link's query string before calling this).
    """

    permission_classes = [AllowAny]

    def post(self, request):
        serializer = VerifyEmailSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        try:
            verify_email_token(token=serializer.validated_data["token"])
        except InvalidOrExpiredTokenError as e:
            return Response({"detail": str(e)}, status=status.HTTP_400_BAD_REQUEST)

        return Response(
            {"detail": "Email verified successfully."},
            status=status.HTTP_200_OK,
        )


class RequestPasswordResetView(APIView):
    """
    Requests a password reset. Always returns 200 regardless of whether
    the email is registered — this is deliberate (§14, account
    enumeration protection), not a bug.
    """

    permission_classes = [AllowAny]

    def post(self, request):
        serializer = RequestPasswordResetSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        email = serializer.validated_data["email"]
        request_password_reset(email)

        return Response(
            {"detail": "Password reset link sent if the email exists."},
            status=status.HTTP_200_OK,
        )


class ResetPasswordView(APIView):
    """
    Resets the password given a valid, unexpired token.
    """

    permission_classes = [AllowAny]

    def post(self, request):
        serializer = ResetPasswordSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        token = serializer.validated_data["token"]
        new_password = serializer.validated_data["new_password"]

        try:
            user = reset_password(token, new_password)

        except InvalidOrExpiredTokenError:
            return Response(
                {"detail": "This reset link is invalid or has expired."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        except ValidationError as e:
            return Response(
                {"new_password": e.messages},
                status=status.HTTP_400_BAD_REQUEST,
            )

        return Response(
            {"detail": "Password has been reset successfully."},
            status=status.HTTP_200_OK,
        )
