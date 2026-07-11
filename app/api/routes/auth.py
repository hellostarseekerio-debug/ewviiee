"""Authentication endpoints.

Security controls implemented here:
- bcrypt password hashing (never plaintext, never reversible)
- account lockout after repeated failed logins (brute-force defense)
- password policy enforcement on account creation
- rate limiting on the login endpoint
- optional TOTP-based multi-factor authentication (RFC 6238), with
  one-time recovery codes for lost-device recovery
- user creation requires an authenticated admin, EXCEPT for the very first
  user in an empty database (one-time bootstrap so there's a way to create
  the first admin without an already-open registration endpoint). That
  bootstrap user is always forced to the admin role regardless of what the
  request asked for - see `scripts/create_admin.py` for the recommended,
  non-network path to do this instead.

Login flow when MFA is enabled for an account:
    1. POST /api/auth/token (username+password) -> {"mfa_required": true,
       "pending_token": "..."} instead of a usable access token.
    2. POST /api/auth/mfa/verify {pending_token, code} -> normal
       {"access_token": "..."}. `code` may be a 6-digit TOTP code or a
       recovery code.
The pending token is scoped (`scope=mfa_pending`) and rejected by every
other endpoint (see `app.api.deps.get_current_user`), and expires in 5
minutes, so a leaked pending token is far less useful than a real one.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session

from app.api.deps import require_role
from app.api.rate_limit import limiter
from app.api.schemas import (
    MFAConfirmRequest,
    MFADisableRequest,
    MFASetupResponse,
    MFAVerifyRequest,
    TokenResponse,
    UserCreateRequest,
)
from app.core.config import get_settings
from app.core.database import get_db
from app.core.logging_config import record_audit
from app.core.mfa import (
    generate_enrollment,
    hash_recovery_codes,
    verify_and_consume_recovery_code,
    verify_totp_code,
)
from app.core.models import User, UserRole
from app.core.security import (
    MFA_PENDING_EXPIRE_MINUTES,
    SecretBox,
    WeakPasswordError,
    create_access_token,
    decode_access_token,
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
        record_audit(actor=form_data.username, action="login_blocked_locked", success=False)
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

    if user.mfa_enabled:
        # Do not reset lockout/failed-attempt counters yet - the second
        # factor still has to succeed. Issue a narrowly-scoped, short-lived
        # token that only /api/auth/mfa/verify will accept.
        pending_token = create_access_token(
            subject=user.username,
            role=user.role.value,
            expires_minutes=MFA_PENDING_EXPIRE_MINUTES,
            scope="mfa_pending",
        )
        record_audit(actor=user.username, action="login_password_ok_awaiting_mfa")
        return TokenResponse(mfa_required=True, pending_token=pending_token)

    register_successful_login(user)
    db.commit()
    record_audit(actor=user.username, action="login_success")
    token = create_access_token(subject=user.username, role=user.role.value)
    return TokenResponse(access_token=token)


@router.post("/mfa/verify", response_model=TokenResponse)
@limiter.limit(lambda: get_settings().rate_limit_login)
def verify_mfa(request: Request, payload: MFAVerifyRequest, db: Session = Depends(get_db)):
    claims = decode_access_token(payload.pending_token)
    if claims is None or claims.get("scope") != "mfa_pending":
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid or expired MFA session")

    user = db.query(User).filter(User.username == claims.get("sub")).first()
    if user is None or not user.is_active or not user.mfa_enabled:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid or expired MFA session")

    if is_account_locked(user):
        raise HTTPException(status.HTTP_423_LOCKED, "Account is temporarily locked")

    verified = False
    if user.mfa_secret_encrypted:
        secret = SecretBox().decrypt(user.mfa_secret_encrypted)
        verified = verify_totp_code(secret, payload.code)

    if not verified and user.mfa_recovery_codes:
        remaining = verify_and_consume_recovery_code(payload.code, user.mfa_recovery_codes)
        if remaining is not None:
            verified = True
            user.mfa_recovery_codes = remaining
            record_audit(actor=user.username, action="mfa_recovery_code_used")

    if not verified:
        register_failed_login(user)
        db.commit()
        record_audit(actor=user.username, action="mfa_verify_failed", success=False)
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Incorrect authentication code")

    register_successful_login(user)
    db.commit()
    record_audit(actor=user.username, action="login_success_mfa")
    token = create_access_token(subject=user.username, role=user.role.value)
    return TokenResponse(access_token=token)


@router.post("/mfa/setup", response_model=MFASetupResponse)
@limiter.limit(lambda: get_settings().rate_limit_default)
def setup_mfa(request: Request, db: Session = Depends(get_db), current_user: User = Depends(require_role(UserRole.VIEWER))):
    """Begins MFA enrollment for the calling user. Returns a secret (for
    manual entry) and an otpauth:// URI (render as a QR code in the GUI),
    plus one-time recovery codes shown only now. MFA is not yet *required*
    for login until `/api/auth/mfa/confirm` verifies the first code."""
    try:
        box = SecretBox()
    except Exception as exc:
        raise HTTPException(
            status.HTTP_500_INTERNAL_SERVER_ERROR,
            "OAP_ENCRYPTION_KEY is not configured on the server - an administrator must set "
            "it before MFA can be used (see docs/SECURITY.md).",
        ) from exc

    enrollment = generate_enrollment(current_user.username)
    current_user.mfa_pending_secret_encrypted = box.encrypt(enrollment.secret)
    current_user.mfa_recovery_codes = hash_recovery_codes(enrollment.recovery_codes)
    db.commit()

    record_audit(actor=current_user.username, action="mfa_setup_started")
    return MFASetupResponse(
        secret=enrollment.secret,
        otpauth_uri=enrollment.otpauth_uri,
        recovery_codes=enrollment.recovery_codes,
    )


@router.post("/mfa/confirm")
@limiter.limit(lambda: get_settings().rate_limit_login)
def confirm_mfa(
    request: Request,
    payload: MFAConfirmRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(UserRole.VIEWER)),
):
    if is_account_locked(current_user):
        raise HTTPException(status.HTTP_423_LOCKED, "Account is temporarily locked")

    if not current_user.mfa_pending_secret_encrypted:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "No MFA setup in progress - call mfa/setup first")

    secret = SecretBox().decrypt(current_user.mfa_pending_secret_encrypted)
    if not verify_totp_code(secret, payload.code):
        # A stolen session token must not let an attacker brute-force the
        # 6-digit TOTP code with unlimited attempts - count it the same as
        # a failed login so the same lockout policy applies here too.
        register_failed_login(current_user)
        db.commit()
        record_audit(actor=current_user.username, action="mfa_confirm_failed", success=False)
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Incorrect code - check your authenticator app and try again")

    current_user.mfa_secret_encrypted = current_user.mfa_pending_secret_encrypted
    current_user.mfa_pending_secret_encrypted = None
    current_user.mfa_enabled = True
    register_successful_login(current_user)
    db.commit()
    record_audit(actor=current_user.username, action="mfa_enabled")
    return {"mfa_enabled": True}


@router.post("/mfa/disable")
@limiter.limit(lambda: get_settings().rate_limit_login)
def disable_mfa(
    request: Request,
    payload: MFADisableRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(UserRole.VIEWER)),
):
    if is_account_locked(current_user):
        raise HTTPException(status.HTTP_423_LOCKED, "Account is temporarily locked")

    if not verify_password(payload.password, current_user.hashed_password):
        # Same reasoning as mfa/confirm above: a stolen session token must
        # not allow unlimited password guesses via this endpoint, bypassing
        # the lockout that the login endpoint enforces.
        register_failed_login(current_user)
        db.commit()
        record_audit(actor=current_user.username, action="mfa_disable_failed", success=False)
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Incorrect password")

    current_user.mfa_enabled = False
    current_user.mfa_secret_encrypted = None
    current_user.mfa_pending_secret_encrypted = None
    current_user.mfa_recovery_codes = None
    register_successful_login(current_user)
    db.commit()
    record_audit(actor=current_user.username, action="mfa_disabled")
    return {"mfa_enabled": False}


@router.post("/admin/users/{username}/mfa/reset")
def admin_reset_mfa(
    username: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(UserRole.ADMIN)),
):
    """Recovery path for a lost authenticator device: an administrator can
    force-disable MFA for another user, who can then re-enroll."""
    target = db.query(User).filter(User.username == username).first()
    if target is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "User not found")
    target.mfa_enabled = False
    target.mfa_secret_encrypted = None
    target.mfa_pending_secret_encrypted = None
    target.mfa_recovery_codes = None
    db.commit()
    record_audit(
        actor=current_user.username, action="mfa_admin_reset", resource_type="user",
        resource_id=target.id, detail={"target_username": username},
    )
    return {"mfa_enabled": False}


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
