from celery import shared_task
from django.core.mail import send_mail
from django.conf import settings


@shared_task
def send_email_verification_email(user_email, verification_url):
    """
    this celery task is used to send email verification email to the user after registration
    """
    send_mail(
        subject="Email Verification",
        message=f"Please verify your email by clicking on the following link: {verification_url}",
        from_email=settings.DEFAULT_FROM_EMAIL,
        recipient_list=[user_email],
        fail_silently=False,
    )


@shared_task
def send_password_reset_email(user_email, reset_url):
    """
    this celery task is used to send password reset email to the user after requesting password reset
    """
    send_mail(
        subject="Password Reset Request",
        message=f"You requested a password reset. Please click on the following link to reset your password: {reset_url}",
        from_email=settings.DEFAULT_FROM_EMAIL,
        recipient_list=[user_email],
        fail_silently=False,
    )
