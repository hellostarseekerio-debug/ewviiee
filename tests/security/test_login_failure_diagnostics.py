"""Covers the login-failure diagnostics added while debugging a reported
"bootstrap ran but login still fails" case: the audit log now records
*why* a login failed (no such account / inactive / wrong password) so an
operator with only stdout log access (e.g. Render's free tier, no Shell,
no DB access) can tell these apart - while the HTTP response to the
client stays the same generic message in every case, so an unauthenticated
caller can never use this to enumerate valid usernames."""
from __future__ import annotations

from app.core.database import session_scope
from app.core.models import AuditLog


def _latest_login_failed_detail(username: str) -> dict:
    with session_scope() as db:
        event = (
            db.query(AuditLog)
            .filter(AuditLog.action == "login_failed", AuditLog.actor == username)
            .order_by(AuditLog.created_at.desc())
            .first()
        )
        assert event is not None, f"no login_failed audit event recorded for {username!r}"
        return dict(event.detail or {})


def test_login_response_is_generic_regardless_of_reason(api_client):
    """The client-facing message must never change based on *why* it
    failed - this is what stops an unauthenticated caller from using the
    error to enumerate which usernames exist."""
    no_such_user = api_client.post("/api/auth/token", data={"username": "nobody", "password": "whatever123!"})
    assert no_such_user.status_code == 401
    assert no_such_user.json()["detail"] == "Incorrect username or password"


def test_audit_log_distinguishes_no_such_account(api_client):
    api_client.post("/api/auth/token", data={"username": "totally-unknown-user", "password": "whatever123!A"})
    assert _latest_login_failed_detail("totally-unknown-user")["reason"] == "no_account_with_this_username"


def test_audit_log_distinguishes_wrong_password(bootstrap_admin):
    api_client, _headers = bootstrap_admin
    api_client.post("/api/auth/token", data={"username": "admin", "password": "DefinitelyWrongPassword1!"})
    assert _latest_login_failed_detail("admin")["reason"] == "password_did_not_match"


def test_audit_log_distinguishes_inactive_account(bootstrap_admin):
    from app.core.models import User

    api_client, headers = bootstrap_admin
    api_client.post(
        "/api/auth/admin/users",
        json={"username": "inactive_user", "password": "SuperSecret123!", "role": "viewer"},
        headers=headers,
    )
    with session_scope() as db:
        db.query(User).filter(User.username == "inactive_user").update({"is_active": False})

    api_client.post("/api/auth/token", data={"username": "inactive_user", "password": "SuperSecret123!"})
    assert _latest_login_failed_detail("inactive_user")["reason"] == "account_is_inactive"
