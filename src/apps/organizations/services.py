import secrets
import hashlib
from datetime import timezone
from django.db import transaction
from django.utils.text import slugify
from django.db import IntegrityError
from apps.organizations.models import Organization, MemberShip, OrganizationInvitation
from apps.organizations.permissions import get_active_membership, ROLE_RANK
from apps.organizations.tasks import send_invitation_email

# ====================== Exception part =====================


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


class InvitationServiceError(OrganizationServiceError):
    pass


class DuplicatePendingInvitationError(InvitationServiceError):
    pass


class InvalidOrExpiredInvitationError(InvitationServiceError):
    pass


class InvitationAlreadyHandledError(InvitationServiceError):
    pass


# ===================== organization creation services =====================


def create_organization(*, owner, name):
    """
    Creates a new Organization and its founding Membership (role=OWNER)
    atomically. An organization with zero owners must never be an
    observable state, even momentarily — see architecture doc §18 ADR #1.
    """
    with transaction.atomic():
        organization = Organization.objects.create(
            name=name, slug=_generate_unique_slug(name)
        )

        MemberShip.objects.create(
            organization=organization,
            user=owner,
            role=MemberShip.Role.OWNER,
            status=MemberShip.Status.ACTIVE,
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
        raise InsufficientRoleError(
            "Only ADMIN or OWNER can update organization details."
        )

    allowed_fields = {"name"}
    for field, value in fields.items():
        if field not in allowed_fields:
            raise ValueError(
                f"Cannot update field '{field}' via update_organization()."
            )
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
        raise InsufficientRoleError(
            "Only ADMIN or OWNER can update organization settings."
        )

    setting_obj = organization.settings
    allowed_fields = {"default_task_status", "allow_public_signup", "custom_branding"}

    # here we loop through the fields to update and check if they are allowed, then set them on the settings object
    for field, value in fields.items():
        if field not in allowed_fields:
            raise ValueError(
                f"Cannot update field '{field}' via update_organization_settings()."
            )
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
        raise InsufficientRoleError(
            "OWNER cannot be granted via change_member_role(); "
            "ownership transfer requires a dedicated, more sensitive flow."
        )

    organization = membership.organization
    actor_membership = get_active_membership(actor, organization)
    if actor_membership is None:
        raise NotAMemberError("You are not a member of this organization.")

    if actor_membership.id == membership.id:
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

    if membership.role == MemberShip.Role.OWNER:
        # Owners are peers — only another OWNER may remove an OWNER.
        # The strict "must outrank" rule below doesn't apply here; the
        # actual safety net for owners is the last-owner check, not rank.
        if actor_membership.role != MemberShip.Role.OWNER:
            raise InsufficientRoleError(
                "Only an OWNER can remove another OWNER from the organization."
            )

    else:
        if ROLE_RANK[actor_membership.role] <= ROLE_RANK[membership.role]:
            raise InsufficientRoleError(
                "You cannot remove a member with a role equal to or above your own."
            )

    with transaction.atomic():
        if membership.role == MemberShip.Role.OWNER:
            remaining_owners = (
                MemberShip.objects.filter(
                    organization=organization,
                    role=MemberShip.Role.OWNER,
                    status=MemberShip.Status.ACTIVE,
                )
                .exclude(pk=membership.pk)
                .exists()
            )

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
            remaining_owners = (
                MemberShip.objects.filter(
                    organization=organization,
                    role=MemberShip.Role.OWNER,
                    status=MemberShip.Status.ACTIVE,
                )
                .exclude(pk=actor_membership.pk)
                .exists()
            )

            if not remaining_owners:
                raise CannotRemoveLastOwnerError(
                    "Cannot leave the organization as the last OWNER."
                )

        actor_membership.delete()


def _generate_token():
    """
    Generates a secure random token for invitations.
    """
    return secrets.token_urlsafe(32)


def _hash_token(token):
    """
    Hashes the token using SHA-256 for secure storage.
    """
    return hashlib.sha256(token.encode()).hexdigest()


def invite_member(*, actor, organization, email, role):
    """
    Invites a new member to an organization by creating an Invitation
    record. The invited user will receive an email with a unique token
    to accept the invitation and join the organization.
    """
    actor_membership = get_active_membership(actor, organization)

    if actor_membership is None:
        raise NotAMemberError("You are not a member of this organization.")

    if ROLE_RANK[actor_membership.role] not in (
        ROLE_RANK[MemberShip.Role.ADMIN],
        ROLE_RANK[MemberShip.Role.OWNER],
    ):
        raise InsufficientRoleError(
            "Only ADMIN or OWNER can invite new members to the organization."
        )

    if role not in (
        MemberShip.Role.ADMIN,
        MemberShip.Role.MANAGER,
        MemberShip.Role.MEMBER,
    ):
        raise InvitationServiceError(
            f"'{role}' is not a valid role to invite a member as."
        )

    if ROLE_RANK[actor_membership.role] <= ROLE_RANK[role]:
        raise InsufficientRoleError(
            "You cannot invite a member with a role equal to or above your own."
        )

    # normalize the email to lowercase for consistency
    # check if the email is already a member or has a pending invitation

    normalized_email = email.strip().lower()
    already_member = MemberShip.objects.filter(
        organization=organization,
        user__email=normalized_email,
        status=MemberShip.Status.ACTIVE,
    ).exists()
    pending_invitation = organization.invitations.filter(
        email=normalized_email, status=OrganizationInvitation.Status.PENDING
    ).exists()

    if already_member:
        raise InvitationServiceError(
            f"The email '{normalized_email}' is already a member of the organization."
        )

    if pending_invitation:
        raise DuplicatePendingInvitationError(
            f"There is already a pending invitation for '{normalized_email}'."
        )

    with transaction.atomic():
        raw_token = _generate_token()
        token_hash = _hash_token(raw_token)

        try:
            invitation = OrganizationInvitation.objects.create(
                organization=organization,
                email=normalized_email,
                invited_by=actor,
                role=role,
                token_hash=token_hash,
                status=OrganizationInvitation.Status.PENDING,
                expires_at=timezone.now()
                + timezone.timedelta(days=7),  # Example: invitation expires in 7 days
            )
        except IntegrityError as e:
            raise DuplicatePendingInvitationError(
                f"There is already a pending invitation for '{normalized_email}'."
            )
    # sending the email
    send_invitation_email.delay_on_commit(invitation.id, raw_token)

    return invitation


def accept_invitation(*, token, user):
    """..."""
    token_hash = _hash_token(token)

    with transaction.atomic():
        try:
            invitation = OrganizationInvitation.objects.select_for_update().get(
                token_hash=token_hash
            )
        except OrganizationInvitation.DoesNotExist:
            raise InvalidOrExpiredInvitationError(
                "Invalid or expired invitation token."
            )

        if invitation.status != OrganizationInvitation.Status.PENDING:
            raise InvitationAlreadyHandledError(
                "This invitation has already been handled."
            )

        if invitation.expires_at < timezone.now():
            raise InvalidOrExpiredInvitationError("This invitation has expired.")

        if user.email.strip().lower() != invitation.email:
            raise InvitationServiceError(
                "This invitation was not issued to your account."
            )

        already_member = MemberShip.objects.filter(
            organization=invitation.organization, user=user
        ).exists()

        if already_member:
            raise InvitationServiceError(
                "You are already a member of this organization."
            )

        membership = MemberShip.objects.create(
            organization=invitation.organization,
            user=user,
            role=invitation.role,
            status=MemberShip.Status.ACTIVE,
        )

        invitation.status = OrganizationInvitation.Status.ACCEPTED
        invitation.accepted_at = timezone.now()
        invitation.save(update_fields=["status", "accepted_at", "updated_at"])

    return membership


def revoke_invitation(*, actor, invitation):
    """
    Revokes a pending invitation. Only the inviter or an ADMIN/OWNER
    of the organization can revoke an invitation.
    """
    organization = invitation.organization
    actor_membership = get_active_membership(actor, organization)

    if actor_membership is None:
        raise NotAMemberError("You are not a member of this organization.")

    if actor_membership.role not in (MemberShip.Role.ADMIN, MemberShip.Role.OWNER):
        raise InsufficientRoleError(
            "Only the inviter or an ADMIN/OWNER can revoke this invitation."
        )

    with transaction.atomic():
        invitation = OrganizationInvitation.objects.select_for_update().get(
            pk=invitation.pk
        )

        if invitation.status != OrganizationInvitation.Status.PENDING:
            raise InvitationAlreadyHandledError(
                "This invitation has already been handled."
            )

        invitation.status = OrganizationInvitation.Status.REVOKED
        invitation.save(update_fields=["status", "updated_at"])
