from django.db import transaction, IntegrityError

from apps.accounts.models import User


class EmailAlreadyRegisteredError(Exception):
    """Domain error: registration attempted with an email that already exists."""


@transaction.atomic
def register_user(*, email: str, password: str, first_name: str = "", last_name: str = "") -> User:
    """
    Register a new user with the provided email, password, first name, and last name.
    Raises EmailAlreadyRegisteredError if the email is already in use.
    """
    normalized_email = email.strip().lower()  # Normalize email to lowercase
    if User.objects.filter(email=normalized_email).exists():
        raise EmailAlreadyRegisteredError(f"The email '{normalized_email}' is already registered.")
    try:
        user = User.objects.create_user(
            email=normalized_email,
            password=password,
            first_name=first_name.strip(),
            last_name=last_name.strip(),
        )
        return user
    except IntegrityError:
        raise EmailAlreadyRegisteredError(f"The email '{normalized_email}' is already registered.")