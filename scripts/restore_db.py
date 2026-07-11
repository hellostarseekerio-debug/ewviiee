"""Restores the SQLite database and archive/export directories from a
backup produced by `scripts/backup_db.py`.

Usage:
    python scripts/restore_db.py data/backups/backup_20260711T120000Z.tar.gz
    python scripts/restore_db.py data/backups/backup_20260711T120000Z.tar.gz --yes

This is a destructive operation on the *current* data, so:
1. It always makes a safety backup of the current state first (via
   `create_backup()`), so a restore can itself be undone.
2. It prompts for confirmation unless `--yes` is passed (for unattended/
   scripted use, e.g. a disaster-recovery runbook).

For PostgreSQL, only the archive/export directories are restored here -
restore the database itself with `pg_restore`.
"""
from __future__ import annotations

import argparse
import shutil
import sys
import tarfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.core.config import DatabaseBackend, Settings, get_settings
from scripts.backup_db import create_backup


def restore_backup(archive_path: Path, settings: Settings) -> None:
    if not archive_path.exists():
        raise FileNotFoundError(f"Backup file not found: {archive_path}")

    with tarfile.open(archive_path, "r:gz") as tar:
        extract_dir = settings.backup_dir / f"_restore_tmp_{archive_path.stem}"
        extract_dir.mkdir(parents=True, exist_ok=True)
        tar.extractall(extract_dir, filter="data")

        db_backup = extract_dir / "office_automation.db"
        if settings.database_backend != DatabaseBackend.POSTGRESQL and db_backup.exists():
            settings.sqlite_path.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(db_backup, settings.sqlite_path)

        archive_backup = extract_dir / "archive"
        if archive_backup.exists():
            if settings.archive_root.exists():
                shutil.rmtree(settings.archive_root)
            shutil.copytree(archive_backup, settings.archive_root)

        export_backup = extract_dir / "export"
        if export_backup.exists():
            if settings.export_root.exists():
                shutil.rmtree(settings.export_root)
            shutil.copytree(export_backup, settings.export_root)

        shutil.rmtree(extract_dir)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("backup_file", type=Path)
    parser.add_argument("--yes", action="store_true", help="Skip the confirmation prompt")
    args = parser.parse_args()

    settings = get_settings()

    if not args.yes:
        confirm = input(
            f"This will OVERWRITE the current database and archive/export data at "
            f"{settings.data_dir} with the contents of {args.backup_file}.\n"
            "A safety backup of the current state will be taken first. Continue? [y/N] "
        )
        if confirm.strip().lower() != "y":
            print("Aborted.")
            return

    safety_backup = create_backup(settings)
    print(f"Safety backup of current state written to {safety_backup}")

    restore_backup(args.backup_file, settings)
    print(f"Restored from {args.backup_file}. Restart the API/GUI to pick up the restored data.")


if __name__ == "__main__":
    main()
