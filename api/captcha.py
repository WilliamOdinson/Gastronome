"""
CAPTCHA text generator.

Produces a cryptographically random alphanumeric string used as the
verification code embedded in CAPTCHA images returned by :func:`api.views.get_captcha_image`.
"""

import secrets
import string


def generate_captcha_text(length: int = 4) -> str:
    charset = string.ascii_letters + string.digits
    return ''.join(secrets.choice(charset) for _ in range(length))
