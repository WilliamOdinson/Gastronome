from celery import shared_task
from django.core.mail import send_mail


@shared_task(queue="email")
def send_verification_email(email: str, verification_code: str) -> None:
    """Dispatch the account-verification e-mail asynchronously."""
    send_mail(
        subject="Gastronome Account Verification",
        message=(
            "Hello,\n\n"
            "Thank you for registering with Gastronome.\n"
            "To complete your account setup, please enter the verification code below:\n\n"
            f"    {verification_code}\n\n"
            "This code will expire in 10 minutes. "
            "If you did not request this code, simply disregard this message "
            "or contact our support team at support@gastronome.com.\n\n"
            "Best regards,\n"
            "The Gastronome Team"
        ),
        from_email="no-reply@gastronome.com",
        recipient_list=[email],
        fail_silently=False,
    )
