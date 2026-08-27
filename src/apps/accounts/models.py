from django.conf import settings
from django.contrib.auth.models import AbstractBaseUser, PermissionsMixin
from django.db import models
from django.utils import timezone
from apps.accounts.managers import UserManager
from common.models import BaseModel
from config.settings.base import AUTH_USER_MODEL


class User(AbstractBaseUser, PermissionsMixin, BaseModel):
    """
    Custom user model that uses email as the unique identifier instead of username.
    """

    email = models.EmailField(unique=True)
    first_name = models.CharField(max_length=30, blank=True)
    last_name = models.CharField(max_length=30, blank=True)
    is_active = models.BooleanField(default=True)
    is_staff = models.BooleanField(default=False)
    is_email_verified = models.BooleanField(default=False)

    objects = UserManager()

    USERNAME_FIELD = "email"
    REQUIRED_FIELDS = []

    def __str__(self):
        return self.email



class AbstractTokenModel(BaseModel):
    """
    Abstract base model for token-based models like EmailVerificationToken and PasswordResetToken.
    It defines common fields and behavior for token models.
    """

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE,related_name="%(class)ss")
    token_hash = models.CharField(max_length=255, unique=True)
    expires_at = models.DateTimeField()
    used_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        abstract = True
        indexes = [
            models.Index(fields=["user"])
        ]

    @property
    def is_expired(self):
        return self.expires_at <= timezone.now()


    @property
    def is_used(self):
        return self.used_at is not None


    @property
    def is_valid(self):
        return not self.is_expired and not self.is_used

    @property
    def mark_used(self):
        self.used_at = timezone.now()
        self.save(update_fields=["used_at"])


    def __str__(self):
        return f"{self.__class__.__name__}(user={self.user_id}, expires_at={self.expires_at})"


class EmailVerificationToken(AbstractTokenModel):
    """
    Handles email verification tokens issued when a user registers
    or requests a new verification link.
    """
    pass



class PasswordResetToken(AbstractTokenModel):
    """
    Handles password reset tokens issued when a user requests a password reset.
    """
    pass
    