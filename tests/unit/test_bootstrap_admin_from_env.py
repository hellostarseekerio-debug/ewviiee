"""Covers scripts/bootstrap_admin_from_env.py - the Shell-less admin
create/reset path for platforms (e.g. Render's free tier) with no Shell
access to run scripts/create_admin.py interactively."""
from __future__ import annotations

import importlib
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent / "scripts"))
import bootstrap_admin_from_env  # noqa: E402

from app.core.database import init_db, session_scope
from app.core.models import User, UserRole
from app.core.security import verify_password


def _run():
    init_db()
    importlib.reload(bootstrap_admin_from_env)
    bootstrap_admin_from_env.main()


def test_noop_when_neither_env_var_set(monkeypatch):
    monkeypatch.delenv("OAP_BOOTSTRAP_ADMIN_USERNAME", raising=False)
    monkeypatch.delenv("OAP_BOOTSTRAP_ADMIN_PASSWORD", raising=False)
    _run()
    with session_scope() as db:
        assert db.query(User).count() == 0


def test_skips_when_only_username_set(monkeypatch, capsys):
    monkeypatch.setenv("OAP_BOOTSTRAP_ADMIN_USERNAME", "envadmin")
    monkeypatch.delenv("OAP_BOOTSTRAP_ADMIN_PASSWORD", raising=False)
    _run()
    with session_scope() as db:
        assert db.query(User).count() == 0
    assert "must be set together" in capsys.readouterr().err


def test_skips_weak_password_without_crashing(monkeypatch, capsys):
    monkeypatch.setenv("OAP_BOOTSTRAP_ADMIN_USERNAME", "envadmin")
    monkeypatch.setenv("OAP_BOOTSTRAP_ADMIN_PASSWORD", "weak")
    _run()
    with session_scope() as db:
        assert db.query(User).count() == 0
    assert "does not meet the password policy" in capsys.readouterr().err


def test_creates_admin_from_env(monkeypatch, capsys):
    monkeypatch.setenv("OAP_BOOTSTRAP_ADMIN_USERNAME", "envadmin")
    monkeypatch.setenv("OAP_BOOTSTRAP_ADMIN_PASSWORD", "EnvBootstrap123!")
    _run()

    with session_scope() as db:
        user = db.query(User).filter(User.username == "envadmin").first()
        assert user is not None
        assert user.role == UserRole.ADMIN
        assert user.is_active is True
        assert verify_password("EnvBootstrap123!", user.hashed_password)

    output = capsys.readouterr().out
    assert "created from environment variables" in output
    assert "remove OAP_BOOTSTRAP_ADMIN_USERNAME" in output
    assert "EnvBootstrap123!" not in output


def test_resets_existing_locked_user_and_clears_mfa(monkeypatch):
    from datetime import datetime, timedelta

    from app.core.security import hash_password

    init_db()
    with session_scope() as db:
        db.add(
            User(
                username="envadmin",
                hashed_password=hash_password("OldPassword123!"),
                role=UserRole.VIEWER,
                is_active=False,
                failed_login_attempts=5,
                locked_until=datetime.utcnow() + timedelta(hours=1),
                mfa_enabled=True,
                mfa_secret_encrypted="ciphertext",
            )
        )

    monkeypatch.setenv("OAP_BOOTSTRAP_ADMIN_USERNAME", "envadmin")
    monkeypatch.setenv("OAP_BOOTSTRAP_ADMIN_PASSWORD", "BrandNewSecret456!")
    _run()

    with session_scope() as db:
        user = db.query(User).filter(User.username == "envadmin").first()
        assert user.role == UserRole.ADMIN
        assert user.is_active is True
        assert user.failed_login_attempts == 0
        assert user.locked_until is None
        assert user.mfa_enabled is False
        assert user.mfa_secret_encrypted is None
        assert verify_password("BrandNewSecret456!", user.hashed_password)
        assert not verify_password("OldPassword123!", user.hashed_password)
