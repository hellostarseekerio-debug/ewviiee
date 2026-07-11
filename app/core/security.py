"""Encrypted secrets, password hashing, and role-based permission checks."""
from __future__ import annotations

import base64
import os
from datetime import datetime, timedelta, timezone
from functools import wraps
from typing import Any, Callable

from cryptography.fernet import Fernet
from jose import JWTError, jwt
from passlib.context import CryptContext

from app.core.config import get_settings
from app.core.models import UserRole

_pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# Roles ranked lowest -> highest privilege for simple >= comparisons.
_ROLE_RANK = {
    UserRole.VIEWER: 0,
    UserRole.REVIEWER: 1,
    UserRole.EDITOR: 2,
    UserRole.ADMIN: 3,
}


def hash_password(password: str) -> str:
    return _pwd_context.hash(password)


def verify_password(password: str, hashed: str) -> bool:
    return _pwd_context.verify(password, hashed)


def create_access_token(subject: str, role: str, expires_minutes: int | None = None) -> str:
    settings = get_settings()
    expire = datetime.now(timezone.utc) + timedelta(
        minutes=expires_minutes or settings.access_token_expire_minutes
    )
    payload = {"sub": subject, "role": role, "exp": expire}
    return jwt.encode(payload, settings.secret_key, algorithm="HS256")


def decode_access_token(token: str) -> dict[str, Any] | None:
    settings = get_settings()
    try:
        return jwt.decode(token, settings.secret_key, algorithms=["HS256"])
    except JWTError:
        return None


def require_role(minimum_role: UserRole) -> Callable:
    """Decorator enforcing that the calling user's role meets a minimum rank.

    Expects the wrapped function to receive a `current_role: UserRole` kwarg.
    """

    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            current_role = kwargs.get("current_role")
            if current_role is None or _ROLE_RANK[current_role] < _ROLE_RANK[minimum_role]:
                raise PermissionError(
                    f"Requires role >= {minimum_role.value}, got {current_role}"
                )
            return func(*args, **kwargs)

        return wrapper

    return decorator


class SecretBox:
    """Symmetric encryption for secrets at rest (API keys, credentials)."""

    def __init__(self, key: str | None = None) -> None:
        settings = get_settings()
        raw_key = key or settings.encryption_key
        if not raw_key:
            raw_key = base64.urlsafe_b64encode(os.urandom(32)).decode()
        self._fernet = Fernet(raw_key.encode() if len(raw_key) == 44 else _derive_key(raw_key))

    def encrypt(self, plaintext: str) -> str:
        return self._fernet.encrypt(plaintext.encode()).decode()

    def decrypt(self, token: str) -> str:
        return self._fernet.decrypt(token.encode()).decode()


def _derive_key(passphrase: str) -> bytes:
    import hashlib

    digest = hashlib.sha256(passphrase.encode()).digest()
    return base64.urlsafe_b64encode(digest)
