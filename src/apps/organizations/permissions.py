from rest_framework import permissions

from .models import MemberShip, Organization

# Fixed role hierarchy — matches architecture doc §9.
# Higher number = more privilege. Used for "must outrank the role being
# granted/changed" checks in services, and reusable here for permission
# comparisons.
ROLE_RANK = {
    MemberShip.Role.MEMBER: 0,
    MemberShip.Role.MANAGER: 1,
    MemberShip.Role.ADMIN: 2,
    MemberShip.Role.OWNER: 3,
}


def get_active_membership(user, organization):
    """
    Single choke point for "is this user an active member of this org,
    and what's their role" — every permission class and service function
    should go through this rather than querying MemberShip directly, so
    there's exactly one place that defines what "active membership" means.
    """
    if not user or not user.is_authenticated or organization is None:
        return None

    return MemberShip.objects.filter(
        user=user,
        organization=organization,
        status=MemberShip.Status.ACTIVE,
    ).first()


def resolve_organization(view):
    """
    Resolves the target Organization from the URL.

    Checks organization_pk/org_id first (nested routes: memberships,
    settings), and only falls back to `pk` when neither is present —
    this covers the Organization detail view itself, where the
    organization IS the resource being addressed by `pk`. The order
    matters: a membership-detail URL has both organization_pk AND pk
    (pk = membership id there), so organization_pk must win first.
    """
    org_id = (
        view.kwargs.get("organization_pk")
        or view.kwargs.get("org_id")
        or view.kwargs.get("pk")
    )
    if not org_id:
        return None
    return Organization.objects.filter(pk=org_id).first()


class IsOrganizationMember(permissions.BasePermission):
    """
    Layer 1 of the isolation model (§9) — API layer.

    Requires the caller to have an ACTIVE Membership in the organization
    resolved from the URL. Does not trust an organization_id from the
    request body — always re-resolves from the URL/view kwargs.

    On success, attaches `request.membership` so downstream code (views,
    services) doesn't have to re-query it.
    """

    message = "You are not a member of this organization."

    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return False

        organization = resolve_organization(view)
        if organization is None:
            return False

        membership = get_active_membership(request.user, organization)
        if membership is None:
            return False

        # Stash for the view/service layer — avoids a second query.
        request.organization = organization
        request.membership = membership
        return True


def has_role(minimum_role):
    class _HasRole(permissions.BasePermission):
        def has_permission(self, request, view):
            membership = getattr(request, "membership", None)
            if membership is None:
                return False
            return ROLE_RANK.get(membership.role, -1) >= ROLE_RANK.get(minimum_role, -1)

    return _HasRole
