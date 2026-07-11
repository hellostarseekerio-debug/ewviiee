"""TOTP-based multi-factor authentication.

Design notes:
- The TOTP secret is encrypted at rest via `app.core.security.SecretBox`
  (requires `OAP_ENCRYPTION_KEY` to be configured - see docs/SECURITY.md).
  MFA setup fails with a clear message if it isn't, rather than storing an
  unencrypted secret.
- Recovery codes are stored as bcrypt hashes (via the same password
  context as user passwords), never in plaintext, and are shown to the
  user exactly once at generation time.
- Verification uses `pyotp`'s constant-time comparison and a small time
  drift window (1 step either side) to tolerate clock skew between the
  server and the user's authenticator app.
"""
from __future__ import annotations

import secrets
from dataclasses import dataclass

import pyotp

from app.core.security import hash_recovery_code, verify_recovery_code

ISSUER = "Office Automation Platform"
RECOVERY_CODE_COUNT = 10


@dataclass
class MFAEnrollment:
    secret: str
    otpauth_uri: str
    recovery_codes: list[str]  # plaintext - display once, never persisted as-is


def generate_enrollment(username: str) -> MFAEnrollment:
    secret = pyotp.random_base32()
    uri = pyotp.totp.TOTP(secret).provisioning_uri(name=username, issuer_name=ISSUER)
    codes = [secrets.token_hex(4) for _ in range(RECOVERY_CODE_COUNT)]
    return MFAEnrollment(secret=secret, otpauth_uri=uri, recovery_codes=codes)


def hash_recovery_codes(codes: list[str]) -> list[str]:
    return [hash_recovery_code(code) for code in codes]


def verify_totp_code(secret: str, code: str) -> bool:
    if not code or not code.isdigit():
        return False
    return pyotp.TOTP(secret).verify(code, valid_window=1)


def verify_and_consume_recovery_code(code: str, hashed_codes: list[str]) -> list[str] | None:
    """Returns the remaining hashed codes (with the matched one removed) if
    `code` matches one of `hashed_codes`, else None. Callers must persist
    the returned list so each recovery code can only be used once."""
    for index, hashed in enumerate(hashed_codes):
        if verify_recovery_code(code, hashed):
            return hashed_codes[:index] + hashed_codes[index + 1 :]
    return None
