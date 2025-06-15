import time
from celery import shared_task
from celery.utils.log import get_task_logger
from django.core.mail import send_mail

logger = get_task_logger("celery.worker.email")


@shared_task(queue="email", bind=True)
def send_verification_email(self, email: str, verification_code: str) -> None:
    """
    Asynchronously send a verification email to the user.
    """
    start_ts = time.perf_counter()
    logger.debug(
        "verification-email task received email=%s code_len=%d",
        email,
        len(verification_code)
    )

    try:
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
    except Exception:
        logger.exception("failed to send verification email email=%s", email)
        raise  # re-raise the exception to mark the task as failed

    elapsed_ms = (time.perf_counter() - start_ts) * 1000
    logger.info(
        "verification e-mail dispatched email=%s elapsed_ms=%.1f",
        email,
        elapsed_ms
    )
