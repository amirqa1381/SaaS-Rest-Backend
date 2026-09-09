import pytest
from rest_framework.test import APIClient

from apps.organizations.models import MemberShip
from apps.organizations.tests.factories import (
    UserFactory,
    OrganizationFactory,
    MembershipFactory,
)


@pytest.fixture
def api_client():
    return APIClient()


@pytest.fixture
def org_a():
    return OrganizationFactory()


@pytest.fixture
def org_b():
    return OrganizationFactory()


@pytest.fixture
def user_a():
    """A user who belongs only to org_a."""
    return UserFactory()


@pytest.fixture
def user_b():
    """A user who belongs only to org_b."""
    return UserFactory()


@pytest.fixture
def membership_a(org_a, user_a):
    """user_a as an ACTIVE OWNER of org_a."""
    return MembershipFactory(
        organization=org_a, user=user_a, role=MemberShip.Role.OWNER
    )


@pytest.fixture
def membership_b(org_b, user_b):
    """user_b as an ACTIVE OWNER of org_b."""
    return MembershipFactory(
        organization=org_b, user=user_b, role=MemberShip.Role.OWNER
    )


@pytest.fixture
def authed_client_a(api_client, user_a, membership_a):
    """APIClient authenticated as user_a (member of org_a only)."""
    api_client.force_authenticate(user=user_a)
    return api_client


@pytest.fixture
def authed_client_b(api_client, user_b, membership_b):
    """APIClient authenticated as user_b (member of org_b only)."""
    api_client.force_authenticate(user=user_b)
    return api_client
