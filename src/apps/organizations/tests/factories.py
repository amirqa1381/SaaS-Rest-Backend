import factory
from factory.django import DjangoModelFactory

from apps.organizations.models import Organization, MemberShip, OrganizationSettings
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
