from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.permissions import AllowAny
from apps.accounts.serializers import RegisterSerializer, UserSerializer
from apps.accounts.services import (
    register_user,
    EmailAlreadyRegisteredError,
    verify_email,
    InvalidOrExpiredTokenError,
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
    """

    permission_classes = [AllowAny]

    def get(self, request, token):
        # Here you would implement the logic to verify the email using the token
        # For example, you might call a service function that handles the verification
        try:
            user = verify_email(
                token
            )  # Assuming verify_email is a function that verifies the token
            return Response(UserSerializer(user).data, status=status.HTTP_200_OK)
        except InvalidOrExpiredTokenError as e:
            return Response(
                {"detail": str(e)},
                status=status.HTTP_400_BAD_REQUEST,
            )
