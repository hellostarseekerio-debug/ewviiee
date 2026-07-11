"""Authentication endpoints.

Security controls implemented here:
- bcrypt password hashing (never plaintext, never reversible)
- account lockout after repeated failed logins (brute-force defense)
- password policy enforcement on account creation
- rate limiting on the login endpoint
- user creation requires an authenticated admin, EXCEPT for the very first
  user in an empty database (one-time bootstrap so there's a way to create
  the first admin without an already-open registration endpoint). That
  bootstrap user is always forced to the admin role regardless of what the
  request asked for - see `scripts/create_admin.py` for the recommended,
  non-network path to do this instead.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session

from app.api.deps import require_role
from app.api.rate_limit import limiter
from app.api.schemas import TokenResponse, UserCreateRequest
from app.core.config import get_settings
from app.core.database import get_db
from app.core.logging_config import record_audit
from app.core.models import User, UserRole
from app.core.security import (
    WeakPasswordError,
    create_access_token,
    hash_password,
    is_account_locked,
    register_failed_login,
    register_successful_login,
    validate_password_policy,
    verify_password,
)

router = APIRouter(prefix="/api/auth", tags=["auth"])


@router.post("/token", response_model=TokenResponse)
@limiter.limit(lambda: get_settings().rate_limit_login)
def login(request: Request, form_data: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)):
    user = db.query(User).filter(User.username == form_data.username).first()

    if user and is_account_locked(user):
        record_audit(
            actor=form_data.username, action="login_blocked_locked", success=False
        )
        raise HTTPException(
            status.HTTP_423_LOCKED,
            "Account is temporarily locked due to repeated failed login attempts. Try again later.",
        )

    if not user or not user.is_active or not verify_password(form_data.password, user.hashed_password):
        if user:
            register_failed_login(user)
            db.commit()
        record_audit(actor=form_data.username, action="login_failed", success=False)
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Incorrect username or password")

    register_successful_login(user)
    db.commit()
    record_audit(actor=user.username, action="login_success")

    token = create_access_token(subject=user.username, role=user.role.value)
    return TokenResponse(access_token=token)


@router.post("/users", status_code=status.HTTP_201_CREATED)
def create_user(payload: UserCreateRequest, db: Session = Depends(get_db)):
    try:
        validate_password_policy(payload.password)
    except WeakPasswordError as exc:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, str(exc)) from exc

    if db.query(User).filter(User.username == payload.username).first():
        raise HTTPException(status.HTTP_409_CONFLICT, "Username already exists")

    is_bootstrap = db.query(User).count() == 0
    role = UserRole.ADMIN if is_bootstrap else UserRole(payload.role)

    if not is_bootstrap:
        raise HTTPException(
            status.HTTP_403_FORBIDDEN,
            "User creation requires an authenticated administrator. Use "
            "POST /api/auth/admin/users instead, or scripts/create_admin.py.",
        )

    user = User(
        username=payload.username,
        full_name=payload.full_name,
        hashed_password=hash_password(payload.password),
        role=role,
    )
    db.add(user)
    db.commit()
    record_audit(actor=user.username, action="bootstrap_admin_created", resource_id=user.id)
    return {"id": user.id, "username": user.username, "role": role.value}


@router.post("/admin/users", status_code=status.HTTP_201_CREATED)
def admin_create_user(
    payload: UserCreateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(UserRole.ADMIN)),
):
    """Create a new user. Requires an authenticated admin - this is the
    normal (non-bootstrap) path for adding Editor/Reviewer/Viewer/Admin
    accounts."""
    try:
        validate_password_policy(payload.password)
    except WeakPasswordError as exc:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, str(exc)) from exc

    if db.query(User).filter(User.username == payload.username).first():
        raise HTTPException(status.HTTP_409_CONFLICT, "Username already exists")

    user = User(
        username=payload.username,
        full_name=payload.full_name,
        hashed_password=hash_password(payload.password),
        role=UserRole(payload.role),
    )
    db.add(user)
    db.commit()
    record_audit(
        actor=current_user.username,
        action="user_created",
        resource_type="user",
        resource_id=user.id,
        detail={"created_username": user.username, "role": user.role.value},
    )
    return {"id": user.id, "username": user.username, "role": user.role.value}
