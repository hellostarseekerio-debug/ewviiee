"""Admin-configurable runtime settings (DB-backed), layered on top of the
static `.env`-driven Settings object. Used for controls that a Legislative
Council office admin needs to flip live - most importantly the cloud-AI
kill switch - without editing files or restarting the service.
"""
from __future__ import annotations

from sqlalchemy.orm import Session

from app.core.models import SystemSetting

ALLOW_CLOUD_AI = "allow_cloud_ai"
AI_USAGE_LOGGING_ENABLED = "ai_usage_logging_enabled"
DATA_RETENTION_DAYS = "data_retention_days"

_DEFAULTS = {
    ALLOW_CLOUD_AI: "false",
    AI_USAGE_LOGGING_ENABLED: "true",
    DATA_RETENTION_DAYS: "365",
}


def get_setting(db: Session, key: str) -> str:
    row = db.get(SystemSetting, key)
    if row is not None:
        return row.value
    return _DEFAULTS.get(key, "")


def get_bool_setting(db: Session, key: str) -> bool:
    return get_setting(db, key).strip().lower() in {"1", "true", "yes", "on"}


def set_setting(db: Session, key: str, value: str, updated_by: str | None = None) -> None:
    row = db.get(SystemSetting, key)
    if row is None:
        row = SystemSetting(key=key, value=value, updated_by=updated_by)
        db.add(row)
    else:
        row.value = value
        row.updated_by = updated_by
    db.commit()


def all_settings(db: Session) -> dict[str, str]:
    rows = {row.key: row.value for row in db.query(SystemSetting).all()}
    merged = dict(_DEFAULTS)
    merged.update(rows)
    return merged
