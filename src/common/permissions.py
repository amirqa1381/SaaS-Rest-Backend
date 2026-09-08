from rest_framework import permissions


class IsAuthenticatedAndHasOrganization(permissions.BasePermission):
    """
    Bare-minimum request-level gate: the user must be authenticated, and
    the request must have resolved a `request.organization` (set by
    middleware or the view, based on the org in the URL/context).

    This does NOT check whether the user actually belongs to that org —
    that's IsOrganizationMember's job, in apps/organizations/permissions.py.
    This class exists purely so tenant-scoped views have a cheap first
    gate before doing any DB lookups.
    """

    def has_permission(self, request, view):
        return bool(
            request.user
            and request.user.is_authenticated
            and getattr(request, "organization", None) is not None
        )


class IsObjectInUsersOrganization(permissions.BasePermission):
    """
    Object-level safety net — layer 4 of the isolation model (§9).

    Even if a queryset filter were ever missed upstream, this makes sure
    that fetching a specific object by ID from another org still 403s,
    rather than 200s with someone else's data.

    Works on ANY model with an `organization_id` field — i.e. anything
    inheriting TenantScopedModel. Has no knowledge of Membership/roles;
    it only compares the object's org against the org already resolved
    onto the request.
    """

    message = "You do not have access to this resource."

    def has_object_permission(self, request, view, obj):
        org = getattr(request, "organization", None)
        if org is None:
            return False

        obj_org_id = getattr(obj, "organization_id", None)
        if obj_org_id is None:
            # Object has no organization_id at all — this permission
            # class is being used on the wrong kind of model. Fail closed.
            return False

        return obj_org_id == org.id