import threading
import pytest
from django.test import TransactionTestCase
from django.utils import timezone
from django.db import close_old_connections

from apps.organizations.models import OrganizationInvitation, MemberShip
from apps.organizations.services import accept_invitation, InvitationAlreadyHandledError
from .factories import OrganizationInvitationFactory, OrganizationFactory, UserFactory
from apps.organizations.services import _hash_token


class TestAcceptInvitationConcurrency(TransactionTestCase):
    """
    Uses TransactionTestCase (not TestCase) because it does NOT wrap the
    test in a rolled-back transaction — real concurrent DB connections
    from separate threads need to actually commit/see each other's locks,
    which TestCase's transaction wrapping would prevent.
    """

    def test_only_one_concurrent_accept_succeeds(self):
        org = OrganizationFactory()
        user = UserFactory()
        raw_token = "concurrent-test-token"
        invitation = OrganizationInvitationFactory(
            organization=org,
            email=user.email,
            token_hash=_hash_token(raw_token),
            status=OrganizationInvitation.Status.PENDING,
        )

        results = []
        errors = []

        def try_accept():
            close_old_connections()
            try:
                membership = accept_invitation(token=raw_token, user=user)
                results.append(membership)
            except InvitationAlreadyHandledError as e:
                errors.append(e)
            except Exception as e:
                errors.append(e)

        threads = [threading.Thread(target=try_accept) for _ in range(5)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        # exactly one thread should have succeeded
        assert len(results) == 1
        # the rest should have hit InvitationAlreadyHandledError, not a raw IntegrityError
        assert len(errors) == 4
        assert all(isinstance(e, InvitationAlreadyHandledError) for e in errors)

        # exactly one Membership row was created — no duplicates
        assert MemberShip.objects.filter(organization=org, user=user).count() == 1