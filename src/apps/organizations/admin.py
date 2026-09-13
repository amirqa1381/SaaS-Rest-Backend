from django.contrib import admin

from .models import Organization, MemberShip, OrganizationSettings, OrganizationInvitation


@admin.register(Organization)
class OrganizationAdmin(admin.ModelAdmin):
    list_display = ("name", "slug", "status", "created_at")
    search_fields = ("name", "slug")
    list_filter = ("status",)
    readonly_fields = ("created_at", "updated_at")


@admin.register(MemberShip)
class MembershipAdmin(admin.ModelAdmin):
    list_display = ("user", "organization", "role", "status", "joined_at")
    search_fields = ("user__email", "organization__name")
    list_filter = ("role", "status", "organization")
    readonly_fields = ("created_at", "updated_at")
    autocomplete_fields = ("user", "organization")


@admin.register(OrganizationSettings)
class OrganizationSettingsAdmin(admin.ModelAdmin):
    list_display = ("organization", "allow_public_signup")
    search_fields = ("organization__name",)


@admin.register(OrganizationInvitation)
class OrganizationInvitationAdmin(admin.ModelAdmin):
    list_display = (
        "email",
        "organization",
        "role",
        "status",
        "invited_by",
        "expires_at",
        "accepted_at",
        "created_at",
    )
    search_fields = ("email", "organization__name", "invited_by__email")
    list_filter = ("status", "role", "organization")
    readonly_fields = (
        "token_hash",
        "created_at",
        "accepted_at",
    )
    autocomplete_fields = ("organization", "invited_by")
    ordering = ("-created_at",)