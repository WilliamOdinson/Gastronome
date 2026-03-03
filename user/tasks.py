"""
Celery tasks for the ``user`` application.

``prepare_registration`` — decrypts the Fernet-encrypted password,
hashes it with Django's ``make_password``, generates a 6-digit
verification code, and stores the bundle in Redis with a 10-minute TTL.

``send_verification_email`` — dispatches the verification code email
via Django's ``send_mail``. The two tasks are chained together at
registration time so the email is sent only after the cache entry
is safely persisted.
"""

import secrets
import time
from celery import shared_task, chain
from celery.utils.log import get_task_logger
from cryptography.fernet import Fernet, InvalidToken
from django.conf import settings
from django.contrib.auth.hashers import make_password
from django.core.cache import cache
from django.core.mail import send_mail

logger = get_task_logger("celery.worker.account")
FERNET = Fernet(settings.FERNET_KEY.encode())


@shared_task(queue="account", bind=True,
             autoretry_for=(Exception,), retry_backoff=True, max_retries=3)
def prepare_registration(self, email: str, enc_pwd: str, display_name: str) -> dict:
    """
    Prepare the user registration by decrypting the password, hashing it,
    generating a verification code, and storing everything in the cache.
    """
    start = time.perf_counter()

    try:
        raw_password = FERNET.decrypt(enc_pwd.encode(), ttl=600).decode()
    except InvalidToken as exc:
        logger.warning("password decryption failed email=%s err=%s", email, exc)
        raise

    verification_code = "".join(str(secrets.randbelow(10)) for _ in range(6))
    password_hash = make_password(raw_password)

    cache.set(
        f"pending_register:{email}",
        {
            "password_hash": password_hash,
            "display_name": display_name,
            "verification_code": verification_code,
        },
        timeout=600,
    )

    elapsed_ms = (time.perf_counter() - start) * 1000
    logger.info(
        "prepare_registration completed email=%s elapsed_ms=%.1f",
        email,
        elapsed_ms,
    )

    # Hand over to the next task in the chain.
    return {"email": email, "verification_code": verification_code}


@shared_task(queue="account", bind=True,
             autoretry_for=(Exception,), retry_backoff=True, max_retries=5)
def send_verification_email(self, payload: dict) -> None:
    """
    Send a verification email to the user.
    """
    email = payload["email"]
    code = payload["verification_code"]
    start = time.perf_counter()

    try:
        send_mail(
            subject="Gastronome Account Verification",
            message=(
                "Hello,\n\n"
                "Thank you for registering with Gastronome.\n"
                "To complete your account setup, please enter the verification code below:\n\n"
                f"    {code}\n\n"
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

    elapsed_ms = (time.perf_counter() - start) * 1000
    logger.info(
        "verification e-mail dispatched email=%s elapsed_ms=%.1f",
        email,
        elapsed_ms,
    )
