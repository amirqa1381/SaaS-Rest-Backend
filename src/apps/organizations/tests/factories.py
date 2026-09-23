import factory
from factory.django import DjangoModelFactory

from datetime import timedelta
from django.utils import timezone
from apps.organizations.models import Organization, MemberShip, OrganizationInvitation
from apps.accounts.models import User


class UserFactory(DjangoModelFactory):
    class Meta:
        model = User

    email = factory.Sequence(lambda n: f"user{n}@example.com")
    first_name = "Test"
    last_name = "User"
    is_active = True

    @factory.post_generation
    def password(self, create, extracted, **kwargs):
        raw_password = extracted or "TestPass123!"
        self.set_password(raw_password)
        if create:
            self.save()


class OrganizationFactory(DjangoModelFactory):
    class Meta:
        model = Organization

    name = factory.Sequence(lambda n: f"Org {n}")
    slug = factory.Sequence(lambda n: f"org-{n}")
    status = Organization.Status.ACTIVE


class MembershipFactory(DjangoModelFactory):
    class Meta:
        model = MemberShip

    organization = factory.SubFactory(OrganizationFactory)
    user = factory.SubFactory(UserFactory)
    role = MemberShip.Role.MEMBER
    status = MemberShip.Status.ACTIVE


class OrganizationInvitationFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = OrganizationInvitation

    organization = factory.SubFactory("apps.organizations.tests.factories.OrganizationFactory")
    email = factory.Sequence(lambda n: f"invitee{n}@example.com")
    role = OrganizationInvitation.InvitableRole.MEMBER
    token_hash = factory.Sequence(lambda n: f"fake-token-hash-{n}")
    status = OrganizationInvitation.Status.PENDING
    expires_at = factory.LazyFunction(lambda: timezone.now() + timedelta(days=7))