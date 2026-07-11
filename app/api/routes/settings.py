"""Admin-only runtime settings: the cloud-AI kill switch, AI usage logging
toggle, and data retention policy. These are DB-backed (see
`app.core.system_settings`) so they take effect immediately without editing
`.env` or restarting the service."""
from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.deps import require_role
from app.api.schemas import SystemSettingUpdateRequest
from app.core.database import get_db
from app.core.logging_config import record_audit
from app.core.models import UserRole
from app.core.system_settings import all_settings, set_setting

router = APIRouter(prefix="/api/settings", tags=["settings"])


@router.get("")
def get_settings_view(
    db: Session = Depends(get_db), _=Depends(require_role(UserRole.ADMIN))
) -> dict[str, str]:
    return all_settings(db)


@router.put("")
def update_setting(
    payload: SystemSettingUpdateRequest,
    db: Session = Depends(get_db),
    current_user=Depends(require_role(UserRole.ADMIN)),
) -> dict[str, str]:
    set_setting(db, payload.key, payload.value, updated_by=current_user.username)
    record_audit(
        actor=current_user.username,
        action="system_setting_changed",
        resource_type="system_setting",
        resource_id=payload.key,
        detail={"new_value": payload.value},
    )
    return all_settings(db)
