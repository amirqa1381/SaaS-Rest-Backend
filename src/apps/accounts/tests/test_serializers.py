import pytest

from apps.accounts.models import User
from apps.accounts.serializers import RegisterSerializer, UserSerializer

pytestmark = pytest.mark.django_db


class TestRegisterSerializer:
    def test_valid_data_passes(self):
        data = {
            "email": "Valid@Example.com",
            "password": "S0meStr0ngP@ssword!",
            "first_name": "A",
            "last_name": "B",
        }
        serializer = RegisterSerializer(data=data)

        assert serializer.is_valid(), serializer.errors

    def test_email_is_normalized_to_lowercase(self):
        serializer = RegisterSerializer(
            data={"email": "MiXed@Example.COM", "password": "S0meStr0ngP@ssword!"}
        )

        assert serializer.is_valid(), serializer.errors
        assert serializer.validated_data["email"] == "mixed@example.com"

    def test_weak_password_is_rejected(self):
        serializer = RegisterSerializer(
            data={"email": "weak@example.com", "password": "123"}
        )

        assert not serializer.is_valid()
        assert "password" in serializer.errors

    def test_missing_email_is_invalid(self):
        serializer = RegisterSerializer(data={"password": "S0meStr0ngP@ssword!"})

        assert not serializer.is_valid()
        assert "email" in serializer.errors

    def test_missing_password_is_invalid(self):
        serializer = RegisterSerializer(data={"email": "nopass@example.com"})

        assert not serializer.is_valid()
        assert "password" in serializer.errors

    def test_first_and_last_name_are_optional(self):
        serializer = RegisterSerializer(
            data={"email": "noname@example.com", "password": "S0meStr0ngP@ssword!"}
        )

        assert serializer.is_valid(), serializer.errors

    def test_password_is_write_only(self):
        serializer = RegisterSerializer(
            data={"email": "wo@example.com", "password": "S0meStr0ngP@ssword!"}
        )
        serializer.is_valid()

        assert "password" not in serializer.data


class TestUserSerializer:
    def test_serializes_expected_fields_only(self):
        user = User.objects.create_user(
            email="ser@example.com", password="pass12345", first_name="X"
        )

        data = UserSerializer(user).data

        assert set(data.keys()) == {
            "id",
            "email",
            "first_name",
            "last_name",
            "is_active",
            "created_at",
        }
        assert data["email"] == "ser@example.com"

    def test_password_is_never_exposed(self):
        user = User.objects.create_user(email="nopass@example.com", password="pass12345")

        data = UserSerializer(user).data

        assert "password" not in data

    def test_all_fields_are_read_only_on_input(self):
        serializer = UserSerializer(data={"email": "readonly@example.com"})

        assert serializer.is_valid(), serializer.errors
        # Read-only fields are ignored as input, so nothing lands in validated_data
        assert serializer.validated_data == {}