"""Shared FastAPI dependencies: DB session, plugin registry, workflow engine."""
from __future__ import annotations

from functools import lru_cache

from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.models import User, UserRole
from app.core.security import decode_access_token
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
    user = db.query(User).filter(User.username == payload.get("sub")).first()
    if user is None or not user.is_active:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "User not found or inactive")
    return user


def require_role(minimum: UserRole):
    rank = {UserRole.VIEWER: 0, UserRole.REVIEWER: 1, UserRole.EDITOR: 2, UserRole.ADMIN: 3}

    def checker(user: User = Depends(get_current_user)) -> User:
        if rank[user.role] < rank[minimum]:
            raise HTTPException(status.HTTP_403_FORBIDDEN, "Insufficient permissions")
        return user

    return checker
