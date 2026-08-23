import uuid

from django.db import models


class BaseModel(models.Model):
    """
    Every model in the system inherits from this (directly, or via
    TenantScopedModel below). Gives every table a UUID PK and
    created_at/updated_at for free, consistently.

    NOTE:A handful of high-volume,
    never-URL-exposed models (AuditLog, Notification) deliberately use a
    bigint PK instead — those models should NOT inherit from BaseModel;
    define their own `id = models.BigAutoField(primary_key=True)`.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True


class TenantManager(models.Manager):
    """
    Default manager for every tenant-scoped model.

    Deliberately does NOT return all rows from a bare `.objects.all()` /
    `.objects.filter(...)` call without an explicit organization — callers
    must use `.for_organization(org)`. This makes "forgot to scope this
    query by tenant" fail loudly (an empty or clearly-wrong queryset)
    instead of silently leaking cross-tenant rows. See architecture §9.
    """

    def get_queryset(self):
        # Soft-deleted rows are excluded by default everywhere, so that
        # isn't something every call site has to remember (see is_deleted
        # handling in TenantScopedModel).
        qs = super().get_queryset()
        if hasattr(self.model, "is_deleted"):
            qs = qs.filter(is_deleted=False)
        return qs

    def for_organization(self, organization):
        """The only sanctioned way to query a tenant-scoped model's table."""
        return self.get_queryset().filter(organization=organization)


class TenantScopedModel(BaseModel):
    """
    Base class for every model that belongs to exactly one Organization
    (Project, Task, TaskComment, Attachment, Label, ...).

    `organization` is a required FK here (not optional) — a tenant-scoped
    row with no organization is itself a data-integrity bug we want the
    DB to reject, not just the application layer.
    """

    # Using a string reference avoids a circular import; the
    # organizations app is added in Milestone 4.
    organization = models.ForeignKey(
        "organizations.Organization",
        on_delete=models.CASCADE,
        related_name="%(class)ss",
    )
    is_deleted = models.BooleanField(default=False, db_index=True)

    objects = TenantManager()

    class Meta:
        abstract = True
