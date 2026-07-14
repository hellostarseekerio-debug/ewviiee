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
# Deliberately no `from __future__ import annotations` in this file (unlike
# most of the rest of this codebase): every route below decorated with
# `@limiter.limit(...)` is wrapped by slowapi before FastAPI ever sees it,
# and FastAPI resolves PEP 563 deferred string annotations using the
# *decorated* function's `__globals__` - which is slowapi's own module, not
# this one. Every name referenced only by this file's annotations
# (OAuth2PasswordRequestForm, MFAVerifyRequest, MFAConfirmRequest, User,
# etc.) is invisible there, so those annotations silently stayed
# unresolved ForwardRefs and broke route registration at startup (only
# under FastAPI==0.111.0, the version actually pinned for deployment -
# newer FastAPI versions happen to tolerate it, which is why this wasn't
# caught locally against the pinned deployment version until now). Keeping
# annotations as live objects (no future import) sidesteps the whole
# eval/globals mismatch, regardless of decorator wrapping.

from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, require_role
from app.api.rate_limit import limiter
from app.api.schemas import (
    AdminPasswordResetRequest,
    ChangePasswordRequest,
    MFAConfirmRequest,
    MFADisableRequest,
    MFASetupResponse,
    MFAVerifyRequest,
    TokenResponse,
    UserCreateRequest,
    UserOut,
    UserUpdateRequest,
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
def login(
    request: Request,
    # Depends(OAuth2PasswordRequestForm) is written explicitly, not the
    # usual bare `= Depends()`. With `from __future__ import annotations`,
    # this parameter's annotation is a string until FastAPI evaluates it -
    # and it evaluates a *decorated* function's annotations using the
    # decorator's own module globals, not this module's (slowapi's
    # @limiter.limit wraps `login`, and slowapi doesn't import
    # OAuth2PasswordRequestForm). A bare `Depends()` relies on the
    # resolved annotation to know *what* to call, so that lookup failing
    # left it holding an unresolved ForwardRef - which FastAPI then tried
    # to call as the dependency, crashing with "ForwardRef(...) is not a
    # callable object" at startup. Naming the class explicitly here
    # sidesteps that lookup entirely, regardless of which module's
    # globals get used to resolve it.
    form_data: OAuth2PasswordRequestForm = Depends(OAuth2PasswordRequestForm),
    db: Session = Depends(get_db),
):
    user = db.query(User).filter(User.username == form_data.username).first()

    if user and is_account_locked(user):
        record_audit(actor=form_data.username, action="login_blocked_locked", success=False)
        raise HTTPException(
            status.HTTP_423_LOCKED,
            "Account is temporarily locked due to repeated failed login attempts. Try again later.",
        )

    if not user or not user.is_active or not verify_password(form_data.password, user.hashed_password):
        # The HTTP response and the client-facing message deliberately never
        # distinguish these cases (leaking "that account doesn't exist" to
        # an unauthenticated caller is its own information-disclosure risk).
        # But an operator debugging a real "why won't this login work" case
        # from server logs alone (e.g. no Shell/DB access) has no other way
        # to tell them apart, so the *server-side* audit log - which
        # reaches stdout, see record_audit() - safely records which one.
        if user is None:
            reason = "no_account_with_this_username"
        elif not user.is_active:
            reason = "account_is_inactive"
        else:
            reason = "password_did_not_match"
        if user:
            register_failed_login(user)
            db.commit()
        record_audit(actor=form_data.username, action="login_failed", success=False, detail={"reason": reason})
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

    # record_audit() here (~13ms, measured) was tried as a FastAPI
    # BackgroundTask during login-latency profiling, deferring it past the
    # response - rejected: it would let a security audit event (a
    # successful/failed login, a lockout) be silently lost if the process
    # crashes or restarts in the window between "response sent" and
    # "background task actually runs", which is exactly the audit trail
    # this file's own module docstring lists as a security control. 13ms
    # isn't worth trading that guarantee away, so this stays synchronous.
    register_successful_login(user)
    db.commit()
    record_audit(actor=user.username, action="login_success")
    token = create_access_token(subject=user.username, role=user.role.value)
    # Returning the user object here (not just the token) saves the
    # frontend a second sequential round trip to GET /api/auth/me before
    # it can navigate anywhere - see the same profiling.
    return TokenResponse(access_token=token, user=UserOut.model_validate(user))


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
    return TokenResponse(access_token=token, user=UserOut.model_validate(user))


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


@router.get("/me", response_model=UserOut)
def read_current_user(current_user: User = Depends(get_current_user)):
    return current_user


@router.post("/change-password")
@limiter.limit(lambda: get_settings().rate_limit_login)
def change_own_password(
    request: Request,
    payload: ChangePasswordRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Self-service password change - distinct from the admin reset-password
    endpoint, which doesn't require knowing the current password. Rate
    limited the same as login, since it's another endpoint an attacker with
    a stolen session token could otherwise use to brute-force the current
    password with unlimited attempts."""
    if not verify_password(payload.current_password, current_user.hashed_password):
        register_failed_login(current_user)
        db.commit()
        record_audit(actor=current_user.username, action="password_change_failed", success=False)
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Current password is incorrect")

    try:
        validate_password_policy(payload.new_password)
    except WeakPasswordError as exc:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, str(exc)) from exc

    current_user.hashed_password = hash_password(payload.new_password)
    current_user.password_changed_at = datetime.utcnow()
    register_successful_login(current_user)
    db.commit()
    record_audit(actor=current_user.username, action="password_changed")
    return {"detail": "Password changed successfully"}


@router.get("/admin/users", response_model=list[UserOut])
def admin_list_users(
    db: Session = Depends(get_db), _current_user: User = Depends(require_role(UserRole.ADMIN))
):
    return db.query(User).order_by(User.created_at).all()


@router.patch("/admin/users/{username}", response_model=UserOut)
def admin_update_user(
    username: str,
    payload: UserUpdateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(UserRole.ADMIN)),
):
    """Edit full_name/role/is_active for an existing user. An admin cannot
    deactivate or demote their own account through this endpoint - that
    would risk locking every admin out of the office at once if done by
    mistake; use a second admin account for that."""
    target = db.query(User).filter(User.username == username).first()
    if target is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "User not found")

    if target.username == current_user.username and (
        payload.is_active is False or (payload.role is not None and payload.role != UserRole.ADMIN.value)
    ):
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            "You cannot deactivate or demote your own account. Ask another administrator.",
        )

    changes = {}
    if payload.full_name is not None:
        target.full_name = payload.full_name
        changes["full_name"] = payload.full_name
    if payload.role is not None:
        target.role = UserRole(payload.role)
        changes["role"] = payload.role
    if payload.is_active is not None:
        target.is_active = payload.is_active
        changes["is_active"] = payload.is_active

    db.commit()
    record_audit(
        actor=current_user.username, action="user_updated", resource_type="user",
        resource_id=target.id, detail=changes,
    )
    return target


@router.delete("/admin/users/{username}", status_code=status.HTTP_204_NO_CONTENT)
def admin_deactivate_user(
    username: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(UserRole.ADMIN)),
):
    """Deactivates (never hard-deletes) a user - the account and every
    audit log entry it authored must remain for the office's audit trail;
    a deactivated user simply can no longer log in."""
    if username == current_user.username:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "You cannot deactivate your own account.")

    target = db.query(User).filter(User.username == username).first()
    if target is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "User not found")

    target.is_active = False
    db.commit()
    record_audit(
        actor=current_user.username, action="user_deactivated",
        resource_type="user", resource_id=target.id,
    )


@router.post("/admin/users/{username}/reset-password")
def admin_reset_password(
    username: str,
    payload: AdminPasswordResetRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(UserRole.ADMIN)),
):
    try:
        validate_password_policy(payload.new_password)
    except WeakPasswordError as exc:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, str(exc)) from exc

    target = db.query(User).filter(User.username == username).first()
    if target is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "User not found")

    target.hashed_password = hash_password(payload.new_password)
    target.password_changed_at = datetime.utcnow()
    target.failed_login_attempts = 0
    target.locked_until = None
    db.commit()
    record_audit(
        actor=current_user.username, action="admin_password_reset",
        resource_type="user", resource_id=target.id,
    )
    return {"detail": "Password reset successfully"}
