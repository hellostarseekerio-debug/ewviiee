from __future__ import annotations

from datetime import datetime, timedelta

import pytest

from app.core.security import (
    EncryptionKeyMissingError,
    MAX_FAILED_LOGIN_ATTEMPTS,
    SecretBox,
    WeakPasswordError,
    is_account_locked,
    register_failed_login,
    register_successful_login,
    validate_password_policy,
)


class _FakeUser:
    def __init__(self) -> None:
        self.failed_login_attempts = 0
        self.locked_until = None


def test_account_locks_after_max_failed_attempts():
    user = _FakeUser()
    for _ in range(MAX_FAILED_LOGIN_ATTEMPTS - 1):
        register_failed_login(user)
        assert not is_account_locked(user)
    register_failed_login(user)
    assert is_account_locked(user)


def test_successful_login_resets_lockout_state():
    user = _FakeUser()
    user.failed_login_attempts = MAX_FAILED_LOGIN_ATTEMPTS
    user.locked_until = datetime.utcnow() + timedelta(minutes=15)

    register_successful_login(user)

    assert user.failed_login_attempts == 0
    assert user.locked_until is None
    assert not is_account_locked(user)


def test_lockout_expires_after_duration():
    user = _FakeUser()
    user.locked_until = datetime.utcnow() - timedelta(minutes=1)  # already expired
    assert not is_account_locked(user)


@pytest.mark.parametrize(
    "password",
    ["short1!A", "alllowercase123!", "ALLUPPERCASE123!", "NoDigitsHere!!", "NoSpecialChars123"],
)
def test_weak_passwords_rejected(password):
    with pytest.raises(WeakPasswordError):
        validate_password_policy(password)


def test_strong_password_accepted():
    validate_password_policy("Str0ng&Secure-Pass")  # must not raise


def test_secret_box_fails_closed_without_key(monkeypatch):
    monkeypatch.delenv("OAP_ENCRYPTION_KEY", raising=False)
    from app.core.config import get_settings

    get_settings.cache_clear()
    with pytest.raises(EncryptionKeyMissingError):
        SecretBox()
    get_settings.cache_clear()


def test_secret_box_round_trips_with_key():
    box = SecretBox(key="a-test-passphrase-not-used-in-production")
    ciphertext = box.encrypt("super-secret-value")
    assert ciphertext != "super-secret-value"
    assert box.decrypt(ciphertext) == "super-secret-value"
