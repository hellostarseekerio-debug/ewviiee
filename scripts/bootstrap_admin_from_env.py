"""Temporary, environment-variable-driven admin creation/reset - for
deployments where there's no Shell access to run `scripts/create_admin.py`
interactively (e.g. Render's free tier, which doesn't support Shell/SSH).

This is a no-op unless BOTH of the following are set, so it is always safe
to call unconditionally on every container start (see docker/entrypoint.sh):

    OAP_BOOTSTRAP_ADMIN_USERNAME
    OAP_BOOTSTRAP_ADMIN_PASSWORD

When both are set, it creates that user as an admin (or, if the username
already exists, resets its password and forces it back to admin/active/
unlocked - useful for "I forgot my password" recovery too). The password is
validated against the same policy as every other password in this app, and
NEVER logged or echoed anywhere.

This is deliberately NOT an HTTP endpoint - it only runs as a local
process inside the container at startup, so it is never reachable over the
network, and setting the two environment variables already requires the
same Render-dashboard access that Shell would need.

IMPORTANT - remove both environment variables (and redeploy) once you've
logged in with them. Leaving them set means every future restart resets
that account's password back to this same value - anyone who later learns
it (a shared screenshot, a support ticket, a leaked deploy log of a
misconfigured system) could regain access indefinitely for as long as the
variables remain set.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.core.database import init_db, session_scope
from app.core.models import User, UserRole
from app.core.security import WeakPasswordError, hash_password, validate_password_policy


def main() -> None:
    username = os.environ.get("OAP_BOOTSTRAP_ADMIN_USERNAME")
    password = os.environ.get("OAP_BOOTSTRAP_ADMIN_PASSWORD")

    if not username and not password:
        return  # Not requested - the overwhelmingly common case, stay silent.

    if not username or not password:
        print(
            "office-automation-platform: admin bootstrap-from-env skipped - "
            "both OAP_BOOTSTRAP_ADMIN_USERNAME and OAP_BOOTSTRAP_ADMIN_PASSWORD "
            "must be set together (only one was found).",
            file=sys.stderr,
        )
        return

    try:
        validate_password_policy(password)
    except WeakPasswordError as exc:
        # Never blocks startup over this - a typo'd/weak env value should
        # degrade to "bootstrap skipped", not take down the whole app.
        print(
            f"office-automation-platform: admin bootstrap-from-env skipped - "
            f"OAP_BOOTSTRAP_ADMIN_PASSWORD does not meet the password policy: {exc}",
            file=sys.stderr,
        )
        return

    init_db()
    with session_scope() as session:
        existing = session.query(User).filter(User.username == username).first()
        if existing:
            existing.hashed_password = hash_password(password)
            existing.role = UserRole.ADMIN
            existing.is_active = True
            existing.failed_login_attempts = 0
            existing.locked_until = None
            existing.mfa_enabled = False
            existing.mfa_secret_encrypted = None
            existing.mfa_pending_secret_encrypted = None
            existing.mfa_recovery_codes = None
            action = "reset"
        else:
            session.add(
                User(
                    username=username,
                    hashed_password=hash_password(password),
                    role=UserRole.ADMIN,
                )
            )
            action = "created"

    print(f"office-automation-platform: admin account '{username}' {action} from environment variables.")
    print(
        "office-automation-platform: SECURITY - remove OAP_BOOTSTRAP_ADMIN_USERNAME "
        "and OAP_BOOTSTRAP_ADMIN_PASSWORD from this service's environment variables "
        "now and redeploy. Leaving them set resets this password on every restart."
    )


if __name__ == "__main__":
    main()
