"""Tests for TOTP-based multi-factor authentication: enrollment, login flow
gating, recovery codes, and the pending-token scope restriction."""
from __future__ import annotations

import pyotp
import pytest


@pytest.fixture
def encryption_key_env(monkeypatch):
    monkeypatch.setenv("OAP_ENCRYPTION_KEY", "test-only-passphrase-not-for-prod")
    from app.core.config import get_settings

    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


def test_login_without_mfa_returns_access_token_directly(bootstrap_admin):
    client, admin_headers = bootstrap_admin
    response = client.post("/api/auth/token", data={"username": "admin", "password": "SuperSecret123!"})
    assert response.status_code == 200
    body = response.json()
    assert body["access_token"]
    assert body["mfa_required"] is False


def test_mfa_setup_requires_encryption_key(bootstrap_admin):
    client, admin_headers = bootstrap_admin
    response = client.post("/api/auth/mfa/setup", headers=admin_headers)
    assert response.status_code == 500
    assert "OAP_ENCRYPTION_KEY" in response.json()["detail"]


def test_full_mfa_enrollment_and_login_flow(bootstrap_admin, encryption_key_env):
    client, admin_headers = bootstrap_admin

    setup_response = client.post("/api/auth/mfa/setup", headers=admin_headers)
    assert setup_response.status_code == 200
    setup_body = setup_response.json()
    secret = setup_body["secret"]
    assert len(setup_body["recovery_codes"]) == 10

    valid_code = pyotp.TOTP(secret).now()
    confirm_response = client.post(
        "/api/auth/mfa/confirm", json={"code": valid_code}, headers=admin_headers
    )
    assert confirm_response.status_code == 200
    assert confirm_response.json()["mfa_enabled"] is True

    # Password-only login must now return a pending token, not a real one.
    login_response = client.post(
        "/api/auth/token", data={"username": "admin", "password": "SuperSecret123!"}
    )
    assert login_response.status_code == 200
    login_body = login_response.json()
    assert login_body["mfa_required"] is True
    assert login_body["access_token"] is None
    pending_token = login_body["pending_token"]

    # The pending token must not work as a normal bearer token.
    blocked = client.get("/api/documents", headers={"Authorization": f"Bearer {pending_token}"})
    assert blocked.status_code == 401

    # Wrong TOTP code rejected.
    wrong = client.post(
        "/api/auth/mfa/verify", json={"pending_token": pending_token, "code": "000000"}
    )
    assert wrong.status_code == 401

    # Correct TOTP code succeeds.
    correct_code = pyotp.TOTP(secret).now()
    verified = client.post(
        "/api/auth/mfa/verify", json={"pending_token": pending_token, "code": correct_code}
    )
    assert verified.status_code == 200
    final_token = verified.json()["access_token"]
    assert final_token

    whoami = client.get("/api/documents", headers={"Authorization": f"Bearer {final_token}"})
    assert whoami.status_code == 200


def test_recovery_code_is_single_use(bootstrap_admin, encryption_key_env):
    client, admin_headers = bootstrap_admin
    setup_response = client.post("/api/auth/mfa/setup", headers=admin_headers)
    secret = setup_response.json()["secret"]
    recovery_code = setup_response.json()["recovery_codes"][0]

    client.post("/api/auth/mfa/confirm", json={"code": pyotp.TOTP(secret).now()}, headers=admin_headers)

    login = client.post("/api/auth/token", data={"username": "admin", "password": "SuperSecret123!"})
    pending_token = login.json()["pending_token"]

    first_use = client.post(
        "/api/auth/mfa/verify", json={"pending_token": pending_token, "code": recovery_code}
    )
    assert first_use.status_code == 200

    # Re-using the same recovery code must fail on a fresh login attempt.
    login2 = client.post("/api/auth/token", data={"username": "admin", "password": "SuperSecret123!"})
    pending_token2 = login2.json()["pending_token"]
    second_use = client.post(
        "/api/auth/mfa/verify", json={"pending_token": pending_token2, "code": recovery_code}
    )
    assert second_use.status_code == 401


def test_admin_can_reset_mfa_for_locked_out_user(bootstrap_admin, encryption_key_env):
    client, admin_headers = bootstrap_admin
    client.post(
        "/api/auth/admin/users",
        json={"username": "editor1", "password": "EditorPass123!", "role": "editor"},
        headers=admin_headers,
    )
    editor_login = client.post("/api/auth/token", data={"username": "editor1", "password": "EditorPass123!"})
    editor_headers = {"Authorization": f"Bearer {editor_login.json()['access_token']}"}

    setup_response = client.post("/api/auth/mfa/setup", headers=editor_headers)
    secret = setup_response.json()["secret"]
    client.post("/api/auth/mfa/confirm", json={"code": pyotp.TOTP(secret).now()}, headers=editor_headers)

    reset_response = client.post("/api/auth/admin/users/editor1/mfa/reset", headers=admin_headers)
    assert reset_response.status_code == 200

    login_after_reset = client.post(
        "/api/auth/token", data={"username": "editor1", "password": "EditorPass123!"}
    )
    assert login_after_reset.json()["mfa_required"] is False


def test_mfa_confirm_locks_account_after_repeated_wrong_codes(bootstrap_admin, encryption_key_env):
    """A stolen session token must not let an attacker brute-force the
    6-digit TOTP confirmation code with unlimited attempts - this must
    trip the same account lockout that protects the login endpoint."""
    client, admin_headers = bootstrap_admin
    client.post("/api/auth/mfa/setup", headers=admin_headers)

    for _ in range(5):
        response = client.post("/api/auth/mfa/confirm", json={"code": "000000"}, headers=admin_headers)
        assert response.status_code == 400

    # The account is now locked - even a correct-looking request is blocked.
    locked_response = client.post("/api/auth/mfa/confirm", json={"code": "000000"}, headers=admin_headers)
    assert locked_response.status_code == 423


def test_mfa_disable_locks_account_after_repeated_wrong_passwords(bootstrap_admin, encryption_key_env):
    """Same reasoning as mfa/confirm: guessing the account's real password
    via mfa/disable must not bypass the login lockout mechanism."""
    import pyotp as _pyotp

    client, admin_headers = bootstrap_admin
    setup = client.post("/api/auth/mfa/setup", headers=admin_headers)
    client.post(
        "/api/auth/mfa/confirm", json={"code": _pyotp.TOTP(setup.json()["secret"]).now()}, headers=admin_headers
    )

    for _ in range(5):
        response = client.post("/api/auth/mfa/disable", json={"password": "WrongPassword!"}, headers=admin_headers)
        assert response.status_code == 401

    locked_response = client.post(
        "/api/auth/mfa/disable", json={"password": "WrongPassword!"}, headers=admin_headers
    )
    assert locked_response.status_code == 423
