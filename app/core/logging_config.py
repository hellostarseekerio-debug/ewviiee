"""Structured logging + audit trail persistence.

Every import, OCR run, AI decision, validation, export and error is logged
both to the structured application log and to the AuditLog DB table so it
can be reviewed and exported from the GUI.
"""
from __future__ import annotations

import logging
import sys
from logging.handlers import RotatingFileHandler
from pathlib import Path
from typing import Any

import structlog

from app.core.config import get_settings

# A long-running production deployment (this is meant to run for years -
# see docs/architecture.md) writing an unbounded application.log will
# eventually fill the disk. 10 x 20MB rotated files caps this at ~200MB
# while comfortably covering weeks of a single office's activity.
_LOG_MAX_BYTES = 20 * 1024 * 1024
_LOG_BACKUP_COUNT = 10


_configured = False


def configure_logging() -> None:
    global _configured
    if _configured:
        # Idempotent: nothing currently calls this more than once per
        # process, but any caller that did (a script importing both
        # app.api.main and app.gui.main, a future worker process, a
        # test harness) would otherwise accumulate one more file handler
        # per call - every log line duplicated once per accumulated
        # handler, and one more open file descriptor held open forever.
        return

    settings = get_settings()
    log_dir = settings.data_dir / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)

    logging.basicConfig(
        format="%(message)s",
        stream=sys.stdout,
        level=logging.INFO,
    )
    file_handler = RotatingFileHandler(
        log_dir / "application.log",
        maxBytes=_LOG_MAX_BYTES,
        backupCount=_LOG_BACKUP_COUNT,
        encoding="utf-8",
    )
    logging.getLogger().addHandler(file_handler)
    _configured = True

    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,
            structlog.processors.add_log_level,
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.processors.StackInfoRenderer(),
            structlog.processors.format_exc_info,
            structlog.processors.JSONRenderer(),
        ],
        wrapper_class=structlog.make_filtering_bound_logger(logging.INFO),
        context_class=dict,
        logger_factory=structlog.PrintLoggerFactory(),
        cache_logger_on_first_use=True,
    )


def get_logger(name: str) -> structlog.stdlib.BoundLogger:
    return structlog.get_logger(name)


def record_audit(
    actor: str | None,
    action: str,
    resource_type: str | None = None,
    resource_id: str | None = None,
    detail: dict[str, Any] | None = None,
    success: bool = True,
) -> None:
    """Persist an audit event. Never raises - logging failures must not break workflows."""
    from app.core.database import session_scope
    from app.core.models import AuditLog

    logger = get_logger("audit")
    try:
        with session_scope() as session:
            session.add(
                AuditLog(
                    actor=actor,
                    action=action,
                    resource_type=resource_type,
                    resource_id=resource_id,
                    detail=detail,
                    success=success,
                )
            )
    except Exception as exc:  # pragma: no cover - defensive
        logger.error("audit_log_write_failed", error=str(exc), action=action)
    logger.info(
        "audit_event",
        actor=actor,
        action=action,
        resource_type=resource_type,
        resource_id=resource_id,
        success=success,
    )


def export_logs(destination: Path, since: str | None = None) -> Path:
    """Export application + audit logs to a single file for offline review."""
    from app.core.database import session_scope
    from app.core.models import AuditLog

    settings = get_settings()
    app_log = settings.data_dir / "logs" / "application.log"
    destination.parent.mkdir(parents=True, exist_ok=True)

    with destination.open("w", encoding="utf-8") as out:
        out.write("=== Application Log ===\n")
        if app_log.exists():
            out.write(app_log.read_text(encoding="utf-8", errors="replace"))
        out.write("\n=== Audit Log ===\n")
        with session_scope() as session:
            query = session.query(AuditLog).order_by(AuditLog.created_at.desc())
            for entry in query.limit(10000):
                out.write(
                    f"{entry.created_at.isoformat()} | {entry.actor} | {entry.action} | "
                    f"{entry.resource_type}:{entry.resource_id} | success={entry.success}\n"
                )
    return destination
