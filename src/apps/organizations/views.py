from rest_framework import generics, status
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.response import Response

from apps.organizations.models import Organization, MemberShip
from apps.organizations.permissions import IsOrganizationMember, get_active_membership
from apps.organizations.serializers import (
    OrganizationSerializer,
    OrganizationCreateSerializer,
    MembershipSerializer,
    MembershipRoleUpdateSerializer,
    OrganizationSettingsSerializer,
)
from apps.organizations.services import (
    create_organization,
    update_organization,
    update_organization_settings,
    change_member_role,
    remove_member,
    OrganizationServiceError,
    InsufficientRoleError,
    NotAMemberError,
    CannotRemoveLastOwnerError,
    CannotActOnSelfError,
)
from common.permissions import IsObjectInUsersOrganization


def _service_error_response(exc):
    """
    Maps service-layer exceptions to HTTP responses. Centralized here
    so every view handles OrganizationServiceError subclasses the same
    way instead of duplicating try/except blocks per view.
    """

    if isinstance(exc, (NotAMemberError,)):
        return Response({"detail": str(exc)}, status=status.HTTP_403_FORBIDDEN)

    if isinstance(exc, (InsufficientRoleError, CannotActOnSelfError, CannotRemoveLastOwnerError)):
        return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        
    return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)



class OrganizationListCreateView(generics.ListCreateAPIView):
    """
    GET  /api/v1/organizations/   -> orgs the current user belongs to
    POST /api/v1/organizations/   -> create a new org (caller becomes OWNER)

    No IsOrganizationMember here deliberately — there's no single org to
    resolve from the URL on this endpoint. Isolation on GET is enforced
    by filtering the queryset to the caller's own memberships, not by a
    permission class.
    """

    permission_classes = []

    def get_permissions(self):
        from rest_framework.permissions import IsAuthenticated
        return [IsAuthenticated()]


    def get_serializer_class(self):
        if self.request.method == "POST":
            return OrganizationCreateSerializer
        return OrganizationSerializer

    def get_queryset(self):
        """
        Returns the organizations the current user is a member of.
        """
        return Organization.objects.filter(
            memberships__user=self.request.user,
            memberships__status=MemberShip.Status.ACTIVE,
        ).distinct()

    def create(self, request, *args, **kwargs):
        """
        Creates a new organization and makes the current user the owner.
        """
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        try:
            organization = create_organization(
                owner=request.user,
                name=serializer.validated_data["name"],
            )
        except OrganizationServiceError as exc:
            return _service_error_response(exc)

        output_serializer = OrganizationSerializer(organization)
        return Response(output_serializer.data, status=status.HTTP_201_CREATED)




class OrganizationDetailView(generics.RetrieveUpdateAPIView):
    """
    GET   /api/v1/organizations/{pk}/
    PATCH /api/v1/organizations/{pk}/

    permission_classes order matters: IsOrganizationMember (layer 1,
    API-level) runs first and attaches request.organization; then
    IsObjectInUsersOrganization (layer 4, object-level) double-checks
    the fetched object against it — the redundant-by-design isolation
    model from architecture doc §9.
    """
    serializer_class = OrganizationSerializer
    permission_classes = [IsOrganizationMember]
    queryset = Organization.objects.all()

    def patch(self, request, *args, **kwargs):

        organization = self.get_object()

        try:
            updated = update_organization(
                actor=request.user,
                organization=organization,
                **request.data,
            )
        except OrganizationServiceError as exc:
            return _service_error_response(exc)

        output_serializer = OrganizationSerializer(updated)
        return Response(output_serializer.data, status=status.HTTP_200_OK)


class OrganizationSettingsView(generics.RetrieveUpdateAPIView):
    """
    GET   /api/v1/organizations/{organization_pk}/settings/
    PATCH /api/v1/organizations/{organization_pk}/settings/
    """
    serializer_class = OrganizationSettingsSerializer
    permission_classes = [IsOrganizationMember]


    def get_object(self):
        return self.request.organization.settings

    def patch(self, request, *args, **kwargs):
        try:
            updated = update_organization_settings(
                actor=request.user,
                organization=request.organization,
                **request.data,
            )
        except OrganizationServiceError as exc:
            return _service_error_response(exc)

        output_serializer = OrganizationSettingsSerializer(updated)
        return Response(output_serializer.data, status=status.HTTP_200_OK)


class MembershipListView(generics.ListAPIView):
    """
    GET /api/v1/organizations/{organization_pk}/members/
    """
    serializer_class = MembershipSerializer
    permission_classes = [IsOrganizationMember]

    def get_queryset(self):
        return MemberShip.objects.filter(
            organization=self.request.organization,
        ).select_related("user")



class MembershipDetailView(generics.GenericAPIView):
    """
    PATCH  /api/v1/organizations/{organization_pk}/members/{pk}/  -> change role
    DELETE /api/v1/organizations/{organization_pk}/members/{pk}/  -> remove member

    Not RetrieveUpdateDestroyAPIView on purpose — role changes and
    removal both go through the service layer (which does its own
    re-checks per §9), so the generic mixins' default save/delete
    behavior isn't a good fit here.
    """
    serializer_class = MembershipRoleUpdateSerializer
    permission_classes = [IsOrganizationMember]

    def get_object(self):
        return generics.get_object_or_404(MemberShip, pk=self.kwargs["pk"], organization=self.request.organization)

    def patch(self, request, *args, **kwargs):
        membership = self.get_object()
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        try:
            updated = change_member_role(
                actor=request.user,
                membership=membership,
                new_role=serializer.validated_data["role"],
            )
        except OrganizationServiceError as exc:
            return _service_error_response(exc)

        output_serializer = MembershipSerializer(updated)
        return Response(output_serializer.data, status=status.HTTP_200_OK)

    def delete(self, request, *args, **kwargs):
        membership = self.get_object()

        try:
            remove_member(
                actor=request.user,
                membership=membership,
            )
        except OrganizationServiceError as exc:
            return _service_error_response(exc)

        return Response(status=status.HTTP_204_NO_CONTENT)