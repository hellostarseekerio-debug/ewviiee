"""Creates a timestamped backup of the SQLite database plus the archive and
export directories, and prunes backups older than the configured retention
period. For PostgreSQL, this only reminds you to use `pg_dump` (a live
Postgres server can't be safely copied as a file).

Usage:
    python scripts/backup_db.py

Restore instructions: see docs/admin_guide.md "Backups" section.
Intended to be run on a schedule (cron / Windows Task Scheduler).
"""
from __future__ import annotations

import sys
import tarfile
from datetime import datetime, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.core.config import DatabaseBackend, get_settings


def main() -> None:
    settings = get_settings()

    if settings.database_backend == DatabaseBackend.POSTGRESQL:
        print(
            "Database backend is PostgreSQL - use `pg_dump` for the database itself.\n"
            "This script will still back up the archive/export directories."
        )

    settings.backup_dir.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.utcnow().strftime("%Y%m%dT%H%M%SZ")
    archive_name = settings.backup_dir / f"backup_{timestamp}.tar.gz"

    with tarfile.open(archive_name, "w:gz") as tar:
        if settings.database_backend != DatabaseBackend.POSTGRESQL and settings.sqlite_path.exists():
            tar.add(settings.sqlite_path, arcname="office_automation.db")
        if settings.archive_root.exists():
            tar.add(settings.archive_root, arcname="archive")
        if settings.export_root.exists():
            tar.add(settings.export_root, arcname="export")

    print(f"Backup written to {archive_name}")

    cutoff = datetime.utcnow() - timedelta(days=settings.backup_retention_days)
    removed = 0
    for backup_file in settings.backup_dir.glob("backup_*.tar.gz"):
        if datetime.utcfromtimestamp(backup_file.stat().st_mtime) < cutoff:
            backup_file.unlink()
            removed += 1
    if removed:
        print(f"Pruned {removed} backup(s) older than {settings.backup_retention_days} days.")


if __name__ == "__main__":
    main()
