import uuid 

from django.db import models
from django.conf import settings

from common.models import BaseModel 

class Organization(BaseModel):
    """
    The tenant itself. Does NOT inherit TenantScopedModel — an Organization
    doesn't belong to another organization, it IS the organization.
    """

    class Status(models.TextChoices):
        ACTIVE = "ACTIVE", "Active"
        SUSPENDED = "SUSPENDED", "Suspended"
        DELETED = "DELETED", "Deleted"


    name = models.CharField(max_length=255, unique=True)
    slug = models.SlugField(max_length=255, unique=True)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.ACTIVE)

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = self.name.lower().replace(" ", "-")
        super().save(*args, **kwargs)

    def __str__(self):
        return self.name



class MemberShip(BaseModel):
    """
    Join of User <-> Organization, carrying role.

    Deliberately does NOT inherit TenantScopedModel even though it has an
    `organization` FK — see explanation below the code.
    """
    class Role(models.TextChoices):
        OWNER = "OWNER", "Owner"
        ADMIN = "ADMIN", "Admin"
        MANAGER = "MANAGER", "Manager"
        MEMBER = "MEMBER", "Member"

    class Status(models.TextChoices):
        ACTIVE = "ACTIVE", "Active"
        SUSPENDED = "SUSPENDED", "Suspended"


    organization = models.ForeignKey(Organization, on_delete=models.CASCADE, related_name="memberships")
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="memberships")
    role = models.CharField(max_length=20, choices=Role.choices)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.ACTIVE)
    joined_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["organization", "user"], name="unique_org_membership"
            )
        ]
        indexes = [
            models.Index(fields=["organization", "role"]),
        ]

    def __str__(self):
        return f"{self.user_id} @ {self.organization_id} ({self.role})"





class OrganizationSettings(BaseModel):
    """
    Split from Organization so the hot, frequently-read org row stays small.
    """
    organization = models.OneToOneField(
        Organization, on_delete=models.CASCADE, related_name="settings"
    )
    default_task_status = models.CharField(max_length=50, default="TODO")
    allow_public_signup = models.BooleanField(default=False)
    custom_branding = models.JSONField(null=True, blank=True)

    def __str__(self):
        return f"Settings for {self.organization_id}"