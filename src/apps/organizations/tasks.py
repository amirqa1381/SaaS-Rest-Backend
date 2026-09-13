from celery import shared_task
from django.core.mail import send_mail
from django.conf import settings

from apps.organizations.models import OrganizationInvitation


@shared_task(bind=True, max_retries=3, default_retry_delay=60)
def send_invitation_email(self, invitation_id, invitation_token):
    """
    this celery task is used to send the invitation email to the invited user asynchronously.
    """

    try:
        invitation = OrganizationInvitation.objects.get(id=invitation_id)
    except OrganizationInvitation.DoesNotExist:
        # Handle the case where the invitation does not exist
        return

    try:
        subject = f"You're invited to join {invitation.organization.name}"
        message = (
            f"Hello,\n\n"
            f"You have been invited to join the organization '{invitation.organization.name}' "
            f"with the role of '{invitation.role}'.\n\n"
            f"Please click the link below to accept the invitation:\n"
            f"{settings.FRONTEND_URL}/accept-invitation?token={invitation_token}\n\n"
            f"This invitation will expire on {invitation.expires_at}.\n\n"
            f"Best regards,\n"
        )
        send_mail(subject, message, settings.DEFAULT_FROM_EMAIL, [invitation.email])
    except Exception as exc:
        raise self.retry(exc=exc)
