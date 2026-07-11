"""Encrypted secrets, password hashing, account lockout, and role-based
permission checks."""
from __future__ import annotations

import base64
import re
from datetime import datetime, timedelta, timezone
from typing import Any

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

# Account lockout policy: after this many consecutive failed logins, the
# account is locked for LOCKOUT_DURATION_MINUTES. Resets on any successful login.
MAX_FAILED_LOGIN_ATTEMPTS = 5
LOCKOUT_DURATION_MINUTES = 15

# Password policy: enforced on every account creation / password change.
PASSWORD_MIN_LENGTH = 12


class WeakPasswordError(ValueError):
    """Raised when a password fails the office password policy."""


def validate_password_policy(password: str) -> None:
    """Enforces a minimum-strength password policy suitable for a
    government office: length + character class diversity. Raises
    WeakPasswordError with a human-readable reason if the password fails."""
    if len(password) < PASSWORD_MIN_LENGTH:
        raise WeakPasswordError(f"Password must be at least {PASSWORD_MIN_LENGTH} characters long")
    if not re.search(r"[a-z]", password):
        raise WeakPasswordError("Password must contain a lowercase letter")
    if not re.search(r"[A-Z]", password):
        raise WeakPasswordError("Password must contain an uppercase letter")
    if not re.search(r"\d", password):
        raise WeakPasswordError("Password must contain a digit")
    if not re.search(r"[^\w\s]", password):
        raise WeakPasswordError("Password must contain a special character")


def hash_password(password: str) -> str:
    return _pwd_context.hash(password)


def verify_password(password: str, hashed: str) -> bool:
    return _pwd_context.verify(password, hashed)


def hash_recovery_code(code: str) -> str:
    """MFA recovery codes use the same bcrypt context as passwords - they
    are one-time-use secrets and deserve the same at-rest protection."""
    return _pwd_context.hash(code)


def verify_recovery_code(code: str, hashed: str) -> bool:
    return _pwd_context.verify(code, hashed)


def is_account_locked(user) -> bool:
    """`user` is an app.core.models.User; kept duck-typed to avoid an import cycle."""
    return user.locked_until is not None and user.locked_until > datetime.utcnow()


def register_failed_login(user) -> None:
    user.failed_login_attempts = (user.failed_login_attempts or 0) + 1
    if user.failed_login_attempts >= MAX_FAILED_LOGIN_ATTEMPTS:
        user.locked_until = datetime.utcnow() + timedelta(minutes=LOCKOUT_DURATION_MINUTES)


def register_successful_login(user) -> None:
    user.failed_login_attempts = 0
    user.locked_until = None
    user.last_login_at = datetime.utcnow()


def create_access_token(
    subject: str, role: str, expires_minutes: int | None = None, scope: str = "full"
) -> str:
    """`scope="full"` is a normal, API-usable access token. `scope="mfa_pending"`
    is issued after a correct password but before the second MFA factor is
    verified - `get_current_user` rejects it, only `/api/auth/mfa/verify`
    accepts it, and it is deliberately short-lived (see MFA_PENDING_EXPIRE_MINUTES)."""
    settings = get_settings()
    expire = datetime.now(timezone.utc) + timedelta(
        minutes=expires_minutes or settings.access_token_expire_minutes
    )
    payload = {"sub": subject, "role": role, "scope": scope, "exp": expire}
    return jwt.encode(payload, settings.secret_key, algorithm="HS256")


MFA_PENDING_EXPIRE_MINUTES = 5


def decode_access_token(token: str) -> dict[str, Any] | None:
    settings = get_settings()
    try:
        return jwt.decode(token, settings.secret_key, algorithms=["HS256"])
    except JWTError:
        return None


def role_rank(role: UserRole) -> int:
    """Numeric rank for a role, lowest to highest privilege. The canonical
    RBAC enforcement point for HTTP requests is `app.api.deps.require_role`;
    this helper backs both that and any non-HTTP (GUI, CLI) role checks."""
    return _ROLE_RANK[role]


class EncryptionKeyMissingError(RuntimeError):
    """Raised when SecretBox is used without OAP_ENCRYPTION_KEY configured.

    Deliberately fails closed rather than falling back to a random,
    unpersisted key: a random key would make previously-encrypted secrets
    permanently unreadable after any process restart, silently destroying
    data. Generate one with:
        python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
    """


class SecretBox:
    """Symmetric encryption for secrets at rest (API keys, credentials)."""

    def __init__(self, key: str | None = None) -> None:
        settings = get_settings()
        raw_key = key or settings.encryption_key
        if not raw_key:
            raise EncryptionKeyMissingError(
                "OAP_ENCRYPTION_KEY is not set. Refusing to encrypt/decrypt with a "
                "throwaway key - see EncryptionKeyMissingError docstring."
            )
        self._fernet = Fernet(raw_key.encode() if len(raw_key) == 44 else _derive_key(raw_key))

    def encrypt(self, plaintext: str) -> str:
        return self._fernet.encrypt(plaintext.encode()).decode()

    def decrypt(self, token: str) -> str:
        return self._fernet.decrypt(token.encode()).decode()


def _derive_key(passphrase: str) -> bytes:
    import hashlib

    digest = hashlib.sha256(passphrase.encode()).digest()
    return base64.urlsafe_b64encode(digest)
