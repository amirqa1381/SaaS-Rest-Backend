"""
Base tenant-isolation permission classes.

Fleshed out in Milestone 4 alongside the organizations app (Membership
model doesn't exist yet in this bootstrap milestone). Left as a stub here
so the import path is stable from the start.
"""

from rest_framework.permissions import BasePermission


class IsOrganizationMember(BasePermission):
    """
    Placeholder. Will check that request.user has an active Membership
    row for the organization referenced by the URL/object, per
    architecture §9 (API-layer isolation check).
    """

    def has_permission(self, request, view):
        raise NotImplementedError("Implemented in Milestone 4 (organizations app).")
