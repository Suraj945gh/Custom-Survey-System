"""Passwords and login tokens, using only Python's standard library.

Passwords: PBKDF2-SHA256 with a random salt (never stored in plain text).
Tokens:    "<user id>.<expiry>.<signature>". The signature is an HMAC made with the
           secret key, so a token cannot be faked or edited without the key.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import secrets
import time

from .config import settings

def hash_password(password: str) -> str:
    # The iteration count is stored inside the hash, so changing the setting never breaks old passwords.
    iterations = settings.password_iterations
    salt = secrets.token_bytes(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, iterations)
    return f"pbkdf2_sha256${iterations}${salt.hex()}${digest.hex()}"


def verify_password(password: str, stored: str) -> bool:
    try:
        _, iterations, salt, digest = stored.split("$")
        check = hashlib.pbkdf2_hmac("sha256", password.encode(), bytes.fromhex(salt), int(iterations))
    except (ValueError, TypeError):
        return False
    return hmac.compare_digest(check.hex(), digest)


def _sign(message: str) -> str:
    mac = hmac.new(settings.secret_key.encode(), message.encode(), hashlib.sha256).digest()
    return base64.urlsafe_b64encode(mac).decode().rstrip("=")


def make_token(user_id: int, hours: int | None = None) -> str:
    expires = int(time.time()) + 3600 * (hours if hours is not None else settings.token_hours)
    message = f"{user_id}.{expires}"
    return f"{message}.{_sign(message)}"


def read_token(token: str) -> int | None:
    """The user id inside a valid, unexpired token; otherwise None."""
    try:
        user_id, expires, signature = token.split(".")
        if not hmac.compare_digest(signature, _sign(f"{user_id}.{expires}")):
            return None
        if int(expires) < time.time():
            return None
        return int(user_id)
    except (ValueError, AttributeError):
        return None


def new_link_token() -> str:
    """Random, unguessable token for a respondent's personal survey link."""
    return secrets.token_urlsafe(16)
