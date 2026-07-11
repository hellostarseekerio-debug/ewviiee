"""Shared FastAPI dependencies: DB session, plugin registry, workflow engine."""
from __future__ import annotations

from functools import lru_cache

from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.models import User, UserRole
from app.core.security import decode_access_token, is_account_locked, role_rank
from app.plugins.manager import PluginManager
from app.workflow.engine import WorkflowEngine

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/token", auto_error=False)


@lru_cache
def get_plugin_manager() -> PluginManager:
    manager = PluginManager()
    manager.discover_and_load()
    return manager


def get_workflow_engine(manager: PluginManager = Depends(get_plugin_manager)) -> WorkflowEngine:
    return WorkflowEngine(plugin_registry={p.plugin_id: p for p in manager.list_plugins()})


def get_current_user(
    token: str | None = Depends(oauth2_scheme), db: Session = Depends(get_db)
) -> User:
    if token is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Not authenticated")
    payload = decode_access_token(token)
    if payload is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid or expired token")
    if payload.get("scope", "full") != "full":
        # An MFA-pending token proves only the password step. It must never
        # grant API access - only POST /api/auth/mfa/verify accepts it.
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "MFA verification required")
    user = db.query(User).filter(User.username == payload.get("sub")).first()
    if user is None or not user.is_active:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "User not found or inactive")
    if is_account_locked(user):
        raise HTTPException(status.HTTP_423_LOCKED, "Account is temporarily locked")
    return user


def require_role(minimum: UserRole):
    def checker(user: User = Depends(get_current_user)) -> User:
        if role_rank(user.role) < role_rank(minimum):
            raise HTTPException(status.HTTP_403_FORBIDDEN, "Insufficient permissions")
        return user

    return checker
