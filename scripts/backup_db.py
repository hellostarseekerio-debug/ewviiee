"""Creates a timestamped backup of the SQLite database plus the archive and
export directories, and prunes backups older than the configured retention
period. For PostgreSQL, this only reminds you to use `pg_dump` (a live
Postgres server can't be safely copied as a file).

Usage:
    python scripts/backup_db.py

Restore instructions: see docs/admin_guide.md "Backups" section, or run
`python scripts/restore_db.py <backup_file>`.
Intended to be run on a schedule (cron / Windows Task Scheduler).

The core logic is factored into `create_backup()` so it can be exercised
directly by `tests/integration/test_backup_restore.py` without shelling
out to this script.
"""
from __future__ import annotations

import sys
import tarfile
import uuid
from datetime import datetime, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.core.config import DatabaseBackend, Settings, get_settings


def create_backup(settings: Settings) -> Path:
    """Writes a single timestamped .tar.gz containing the SQLite database
    file (if applicable) plus the archive/export directories. Returns the
    path to the created archive."""
    settings.backup_dir.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.utcnow().strftime("%Y%m%dT%H%M%SZ")
    # A short random suffix guarantees uniqueness even when two backups are
    # created within the same second (e.g. restore's automatic safety
    # backup immediately followed by another backup) - a same-second
    # collision would otherwise silently overwrite the earlier archive.
    unique_suffix = uuid.uuid4().hex[:8]
    archive_path = settings.backup_dir / f"backup_{timestamp}_{unique_suffix}.tar.gz"

    with tarfile.open(archive_path, "w:gz") as tar:
        if settings.database_backend != DatabaseBackend.POSTGRESQL and settings.sqlite_path.exists():
            tar.add(settings.sqlite_path, arcname="office_automation.db")
        if settings.archive_root.exists():
            tar.add(settings.archive_root, arcname="archive")
        if settings.export_root.exists():
            tar.add(settings.export_root, arcname="export")

    return archive_path


def prune_old_backups(settings: Settings) -> int:
    """Deletes backups older than `backup_retention_days`. Returns the count removed."""
    cutoff = datetime.utcnow() - timedelta(days=settings.backup_retention_days)
    removed = 0
    for backup_file in settings.backup_dir.glob("backup_*.tar.gz"):
        if datetime.utcfromtimestamp(backup_file.stat().st_mtime) < cutoff:
            backup_file.unlink()
            removed += 1
    return removed


def main() -> None:
    settings = get_settings()

    if settings.database_backend == DatabaseBackend.POSTGRESQL:
        print(
            "Database backend is PostgreSQL - use `pg_dump` for the database itself.\n"
            "This script will still back up the archive/export directories."
        )

    archive_path = create_backup(settings)
    print(f"Backup written to {archive_path}")

    removed = prune_old_backups(settings)
    if removed:
        print(f"Pruned {removed} backup(s) older than {settings.backup_retention_days} days.")


if __name__ == "__main__":
    main()
