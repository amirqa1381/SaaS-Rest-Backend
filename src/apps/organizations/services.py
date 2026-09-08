
from django.db import transaction
from django.utils.text import slugify
from apps.organizations.models import Organization, MemberShip
from apps.organizations.permissions import get_active_membership, ROLE_RANK



class OrganizationServiceError(Exception):
    """Base class for all organizations-app service errors."""


class NotAMemberError(OrganizationServiceError):
    """Raised when the acting user has no active membership in the org."""


class InsufficientRoleError(OrganizationServiceError):
    """Raised when the actor's role doesn't allow the requested action."""


class CannotRemoveLastOwnerError(OrganizationServiceError):
    """Raised when an action would leave an organization with zero owners."""


class CannotActOnSelfError(OrganizationServiceError):
    """Raised when a user tries to change/remove their own membership."""




def create_organization(*,owner,name):
    """
    Creates a new Organization and its founding Membership (role=OWNER)
    atomically. An organization with zero owners must never be an
    observable state, even momentarily — see architecture doc §18 ADR #1.
    """
    with transaction.atomic():
        organization = Organization.objects.create(
            name=name,
            slug=_generate_unique_slug(name)
        )

        MemberShip.objects.create(
            organization=organization,
            user=owner,
            role=MemberShip.Role.OWNER,
            status=MemberShip.Status.ACTIVE
        )

    return organization


def _generate_unique_slug(name):
    """
    Generates a unique slug from the org name, appending a numeric
    suffix on collision (org-name, org-name-2, org-name-3, ...).
    """
    base_slug = slugify(name)
    slug = base_slug
    suffix = 2

    while Organization.objects.filter(slug=slug).exists():
        slug = f"{base_slug}-{suffix}"
        suffix += 1

    return slug


#  ===================== organization update services =====================

def update_organization(*, actor, organization, **fields):
    """
    Updates basic Organization fields (currently just `name`).
    Only ADMIN or OWNER may update org details.

    Re-checks the actor's membership itself — never trusts that the
    caller (view) already checked, per the architecture doc's four-layer
    isolation model (§9).
    """
    membership = get_active_membership(actor, organization)
    if membership is None:
        raise NotAMemberError("You are not a member of this organization.")

    if ROLE_RANK[membership.role] < ROLE_RANK[MemberShip.Role.ADMIN]:
        raise InsufficientRoleError("Only ADMIN or OWNER can update organization details.")

    allowed_fields = {"name"}
    for field, value in fields.items():
        if field not in allowed_fields:
            raise ValueError(f"Cannot update field '{field}' via update_organization().")
        setattr(organization, field, value)

    organization.save(update_fields=list(fields.keys()) + ["updated_at"])
    return organization



def update_organization_settings(*, actor, organization, **fields):
    """
    Updates OrganizationSettings fields. Only ADMIN or OWNER may update
    settings, same rank requirement as update_organization().
    """
    membership = get_active_membership(actor, organization)

    if not membership:
        raise NotAMemberError("You are not a member of this organization.")

    if ROLE_RANK[membership.role] < ROLE_RANK[MemberShip.Role.ADMIN]:
        raise InsufficientRoleError("Only ADMIN or OWNER can update organization settings.")

    setting_obj = organization.settings
    allowed_fields = {"default_task_status", "allow_public_signup", "custom_branding"}

    # here we loop through the fields to update and check if they are allowed, then set them on the settings object
    for field, value in fields.items():
        if field not in allowed_fields:
            raise ValueError(f"Cannot update field '{field}' via update_organization_settings().")
        setattr(setting_obj, field, value)

    setting_obj.save(update_fields=list(fields.keys()) + ["updated_at"])
    return setting_obj



# =================== member role management services ===================

def change_member_role(*, actor, membership, new_role):
    """
    Changes the role of an existing Membership.

    Security rules (architecture doc §14):
    - actor must be an ACTIVE member of the same organization
    - actor's role must be strictly HIGHER than both the target member's
      CURRENT role and the NEW role being granted — a user can never
      grant a role equal to or above their own
    - OWNER is not grantable through this function at all — ownership
      transfer is a separate, more sensitive operation (left out of
      Milestone 4 scope; flagged as a TODO below)
    - an actor cannot change their own role (prevents self-escalation
      and accidental self-demotion with no one else to fix it)
    """
    if new_role == MemberShip.Role.OWNER:
        raise ValueError("Cannot grant OWNER role via change_member_role().")

    organization = membership.organization
    actor_membership = get_active_membership(actor, organization)
    if actor_membership is None:
        raise NotAMemberError("You are not a member of this organization.")

    if actor_membership.id== membership.id:
        raise CannotActOnSelfError("You cannot change your own membership role.")

    actor_rank = ROLE_RANK[actor_membership.role]
    target_current_rank = ROLE_RANK[membership.role]
    new_rank = ROLE_RANK[new_role]

    if actor_rank <= target_current_rank or actor_rank <= new_rank:
        raise InsufficientRoleError(
            "You cannot change a role to or from a role equal to or above your own."
        )

    with transaction.atomic():
        membership.role = new_role
        membership.save(update_fields=["role", "updated_at"])

    return membership



def remove_member(*, actor, membership):
    """
    Removes (hard-deletes) a Membership from an organization.

    Security rules:
    - actor must be an ACTIVE member with a role strictly higher than
      the member being removed
    - an actor cannot remove themselves via this function (use a
      separate "leave organization" flow, out of scope for Milestone 4)
    - the LAST OWNER of an organization can never be removed — this
      would leave the org in a broken, ownerless state (architecture
      doc §18, ADR #1: "an org with zero owners is a broken observable
      state")
    """
    organization = membership.organization
    actor_membership = get_active_membership(actor, organization)

    if actor_membership is None:
        raise NotAMemberError("You are not a member of this organization.")

    if actor_membership.id == membership.id:
        raise CannotActOnSelfError("You cannot remove yourself from the organization.")

    if ROLE_RANK[actor_membership.role] <= ROLE_RANK[membership.role]:
        raise InsufficientRoleError(
            "You cannot remove a member with a role equal to or above your own."
        )

    with transaction.atomic():
        if membership.role == MemberShip.Role.OWNER:
            remaining_owners = MemberShip.objects.filter(
                organization=organization,
                role=MemberShip.Role.OWNER,
                status=MemberShip.Status.ACTIVE
            ).exclude(pk=membership.pk).exists()

            if not remaining_owners:
                raise CannotRemoveLastOwnerError(
                    "Cannot remove the last OWNER of an organization."
                )

        membership.delete()



def leave_organization(*, actor, organization):
    """
    Lets a user voluntarily leave an organization they belong to.
    Same last-owner protection as remove_member() — an OWNER can only
    leave if at least one other ACTIVE owner remains.
    """
    actor_membership = get_active_membership(actor, organization)

    if actor_membership is None:
        raise NotAMemberError("You are not a member of this organization.")

    with transaction.atomic():
        if actor_membership.role == MemberShip.Role.OWNER:
            remaining_owners = MemberShip.objects.filter(
                organization=organization,
                role=MemberShip.Role.OWNER,
                status=MemberShip.Status.ACTIVE
            ).exclude(pk=actor_membership.pk).exists()

            if not remaining_owners:
                raise CannotRemoveLastOwnerError(
                    "Cannot leave the organization as the last OWNER."
                )

        actor_membership.delete()