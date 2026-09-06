import hashlib
import secrets
from datetime import timedelta
from django.conf import settings
from django.utils import timezone
from django.contrib.auth.password_validation import validate_password
from django.db import transaction, IntegrityError
from django.contrib.auth import get_user_model

from apps.accounts.models import EmailVerificationToken, PasswordResetToken
from apps.accounts.tasks import send_email_verification_email, send_password_reset_email

User = get_user_model()


# ============== configurations ================


TOKEN_BYTES = 32
EMAIL_VERIFICATION_TTL = timedelta(hours=24)
PASSWORD_RESET_TTL = timedelta(hours=1)

# ================= Exceptions =====================


class InvalidOrExpiredTokenError(Exception):
    """Domain error: token is invalid or has expired."""

    pass


class EmailAlreadyRegisteredError(Exception):
    """Domain error: registration attempted with an email that already exists."""


#  ================== helpers =====================


def _generate_token() -> str:
    """Raw, unguessable token — this is what gets emailed to the user.
    Never persisted; only its hash is stored (see AbstractToken)."""
    return secrets.token_urlsafe(TOKEN_BYTES)


def _hash_token(token: str) -> str:
    """SHA-256 hex digest — matches token_hash's max_length=64 on AbstractToken."""
    return hashlib.sha256(token.encode()).hexdigest()


# ================== email verification ==================


def issue_email_verification_token(user: User) -> str:
    """
    Creates a new EmailVerificationToken row and returns the RAW token.
    Caller (view/Celery task) is responsible for emailing it — this
    function never sends anything itself, keeping it testable without
    mocking email.
    """
    raw_token = _generate_token()
    token_hash = _hash_token(raw_token)
    expires_at = timezone.now() + EMAIL_VERIFICATION_TTL

    EmailVerificationToken.objects.create(
        user=user, token_hash=token_hash, expires_at=expires_at
    )
    return raw_token


def verify_email_token(*, token: str) -> User:
    """
    Verifies the provided email verification token.
    If valid, marks the token as used and returns the associated user.
    Raises InvalidOrExpiredTokenError if the token is invalid or expired.
    """
    token_hash = _hash_token(token)
    with transaction.atomic():
        try:
            token_obj = (
                EmailVerificationToken.objects.select_for_update()
                .select_related("user")
                .get(token_hash=token_hash)
            )
        except EmailVerificationToken.DoesNotExist:
            raise InvalidOrExpiredTokenError("The provided token is invalid.")

        if not token_obj.is_valid:
            raise InvalidOrExpiredTokenError(
                "The provided token is either expired or already used."
            )

        # Mark the token as used
        token_obj.mark_used()

        # Mark the user's email as verified
        user = token_obj.user
        user.is_email_verified = True
        user.save(update_fields=["is_email_verified"])

    return user


# ================== password reset ==================


@transaction.atomic
def request_password_reset(*, email: str) -> str | None:
    """
    Issues a password reset token for the user with the given email.
    Returns the RAW token if a matching active user exists, otherwise
    returns None. Callers must NOT let a None result change the HTTP
    response — see request_password_reset docs in views.py.
    """
    email = email.strip().lower()

    try:
        user = User.objects.get(email=email, is_active=True)
    except User.DoesNotExist:
        return None

    raw_token = _generate_token()
    token_hash = _hash_token(raw_token)
    expires_at = timezone.now() + PASSWORD_RESET_TTL

    PasswordResetToken.objects.create(
        user=user, token_hash=token_hash, expires_at=expires_at
    )

    reset_url = f"{settings.FRONTEND_URL}/reset-password?token={raw_token}"
    send_password_reset_email.delay_on_commit(user.email, reset_url)

    return raw_token


def reset_password(token: str, new_password: str) -> User:
    """
    Resets the user's password using the provided password reset token.
    Raises InvalidOrExpiredTokenError if the token is invalid or expired.
    """
    token_hash = _hash_token(token)

    with transaction.atomic():
        try:
            token_obj = (
                PasswordResetToken.objects.select_for_update()
                .select_related("user")
                .get(token_hash=token_hash)
            )
        except PasswordResetToken.DoesNotExist:
            raise InvalidOrExpiredTokenError("The provided token is invalid.")

        if not token_obj.is_valid:
            raise InvalidOrExpiredTokenError(
                "The provided token is either expired or already used."
            )

        # Mark the token as used
        token_obj.mark_used()

        # Reset the user's password
        user = token_obj.user
        validate_password(new_password, user=user)  # Validate the new password
        user.set_password(new_password)
        user.save(update_fields=["password"])

        (
            PasswordResetToken.objects.filter(user=user, used_at__isnull=True)
            .exclude(pk=token_obj.pk)
            .update(used_at=timezone.now())  # Mark all other unused tokens as used
        )
    return user


# ================== register user =====================


@transaction.atomic
def register_user(
    *, email: str, password: str, first_name: str = "", last_name: str = ""
) -> User:
    """
    Register a new user with the provided email, password, first name, and last name.
    Raises EmailAlreadyRegisteredError if the email is already in use.
    """
    normalized_email = email.strip().lower()  # Normalize email to lowercase
    if User.objects.filter(email=normalized_email).exists():
        raise EmailAlreadyRegisteredError(
            f"The email '{normalized_email}' is already registered."
        )
    try:
        user = User.objects.create_user(
            email=normalized_email,
            password=password,
            first_name=first_name.strip(),
            last_name=last_name.strip(),
        )

        email_verification_token = issue_email_verification_token(
            user
        )  # Issue email verification token for the new user
        verification_url = (
            f"{settings.FRONTEND_URL}/verify-email" f"?token={email_verification_token}"
        )
        send_email_verification_email.delay_on_commit(
            user.email, verification_url
        )  # Send verification email asynchronously

        return user
    except IntegrityError:
        raise EmailAlreadyRegisteredError(
            f"The email '{normalized_email}' is already registered."
        )
