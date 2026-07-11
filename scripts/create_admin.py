"""Creates (or resets) an administrator account directly against the
database, without going through the network API. This is the recommended
way to provision the first admin account (and any subsequent one) since it
never exposes an open "create user" HTTP endpoint.

Usage:
    python scripts/create_admin.py --username admin --full-name "Jane Doe"

You will be prompted for a password (not echoed, not passed as an argv
so it never ends up in shell history). The password must satisfy the
office password policy (12+ chars, upper/lower/digit/special character).
"""
from __future__ import annotations

import argparse
import getpass
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.core.database import init_db, session_scope
from app.core.models import User, UserRole
from app.core.security import WeakPasswordError, hash_password, validate_password_policy


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--username", required=True)
    parser.add_argument("--full-name", default=None)
    parser.add_argument(
        "--role",
        default="admin",
        choices=[r.value for r in UserRole],
        help="Defaults to admin; use a lower role to provision non-admin staff accounts.",
    )
    args = parser.parse_args()

    password = getpass.getpass("Password: ")
    confirm = getpass.getpass("Confirm password: ")
    if password != confirm:
        print("Passwords do not match.", file=sys.stderr)
        raise SystemExit(1)

    try:
        validate_password_policy(password)
    except WeakPasswordError as exc:
        print(f"Password rejected: {exc}", file=sys.stderr)
        raise SystemExit(1) from exc

    init_db()
    with session_scope() as session:
        existing = session.query(User).filter(User.username == args.username).first()
        if existing:
            existing.hashed_password = hash_password(password)
            existing.role = UserRole(args.role)
            existing.is_active = True
            existing.failed_login_attempts = 0
            existing.locked_until = None
            print(f"Updated existing user '{args.username}' (role={args.role}).")
        else:
            user = User(
                username=args.username,
                full_name=args.full_name,
                hashed_password=hash_password(password),
                role=UserRole(args.role),
            )
            session.add(user)
            print(f"Created user '{args.username}' (role={args.role}).")


if __name__ == "__main__":
    main()
