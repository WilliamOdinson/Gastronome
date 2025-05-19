import secrets
import string


def generate_captcha_text(length: int = 4) -> str:
    charset = string.ascii_letters + string.digits
    return ''.join(secrets.choice(charset) for _ in range(length))
