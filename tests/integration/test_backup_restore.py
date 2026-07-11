"""Actually exercises backup + restore (not just documents the procedure):
creates real data, backs it up, destroys it, restores it, and verifies the
restored data is byte-identical / row-identical to the original. This is
the "backup and recovery testing" required for a production-readiness
review - a backup script nobody has ever restored from is not a backup
strategy.
"""
from __future__ import annotations

import shutil
import sys
from pathlib import Path

from app.core.config import get_settings
from app.core.database import init_db, reset_engine, session_scope
from app.core.models import Document, DocumentStatus


def _seed_data(settings) -> str:
    init_db()
    settings.archive_root.mkdir(parents=True, exist_ok=True)
    settings.export_root.mkdir(parents=True, exist_ok=True)

    archived_file = settings.archive_root / "HousingEstatePosters" / "sample.pdf"
    archived_file.parent.mkdir(parents=True, exist_ok=True)
    archived_file.write_bytes(b"%PDF-1.4 sample archived content")

    with session_scope() as session:
        document = Document(
            filename="sample.pdf",
            source_path=str(archived_file),
            status=DocumentStatus.ARCHIVED,
            district="Kwun Tong",
            estate="Lam Tin Estate",
            archive_path=str(archived_file),
        )
        session.add(document)
        session.flush()
        document_id = document.id

    return document_id


def test_backup_then_restore_preserves_database_and_files(tmp_path):
    from scripts.backup_db import create_backup
    from scripts.restore_db import restore_backup

    settings = get_settings()
    document_id = _seed_data(settings)

    # Sanity: the row and file exist before we do anything destructive.
    with session_scope() as session:
        assert session.get(Document, document_id) is not None
    archived_file = Path(settings.archive_root / "HousingEstatePosters" / "sample.pdf")
    assert archived_file.read_bytes() == b"%PDF-1.4 sample archived content"

    backup_path = create_backup(settings)
    assert backup_path.exists()

    # Simulate data loss: wipe the live database and archive directory.
    reset_engine()
    settings.sqlite_path.unlink()
    shutil.rmtree(settings.archive_root)
    reset_engine()
    init_db()

    with session_scope() as session:
        assert session.get(Document, document_id) is None  # confirms the wipe actually happened
    assert not archived_file.exists()

    # Restore and verify everything comes back exactly as it was.
    restore_backup(backup_path, settings)
    reset_engine()

    with session_scope() as session:
        restored = session.get(Document, document_id)
        assert restored is not None
        assert restored.district == "Kwun Tong"
        assert restored.estate == "Lam Tin Estate"
        assert restored.status == DocumentStatus.ARCHIVED

    assert archived_file.read_bytes() == b"%PDF-1.4 sample archived content"


def test_restore_cli_takes_a_safety_backup_before_overwriting(monkeypatch, capsys):
    """The restore CLI (scripts/restore_db.py main()) must never be a
    one-way door: it backs up whatever is live *before* overwriting it, so
    a bad restore can itself be undone."""
    settings = get_settings()
    _seed_data(settings)

    from scripts.backup_db import create_backup

    backup_to_restore = create_backup(settings)
    backups_before = set(settings.backup_dir.glob("backup_*.tar.gz"))

    # Change data after the backup so we can prove the restore actually ran.
    with session_scope() as session:
        session.query(Document).first().district = "Sha Tin"

    import scripts.restore_db as restore_module

    monkeypatch.setattr(sys, "argv", ["restore_db.py", str(backup_to_restore), "--yes"])
    restore_module.main()

    backups_after = set(settings.backup_dir.glob("backup_*.tar.gz"))
    new_backups = backups_after - backups_before
    assert len(new_backups) == 1, "restore must create exactly one safety backup of the pre-restore state"

    reset_engine()
    with session_scope() as session:
        assert session.query(Document).first().district == "Kwun Tong"  # restored, not "Sha Tin"

    output = capsys.readouterr().out
    assert "Safety backup" in output
    assert "Restored from" in output


def test_restore_cli_aborts_without_confirmation(monkeypatch):
    settings = get_settings()
    _seed_data(settings)
    from scripts.backup_db import create_backup

    backup_path = create_backup(settings)
    backups_before = set(settings.backup_dir.glob("backup_*.tar.gz"))

    import scripts.restore_db as restore_module

    monkeypatch.setattr(sys, "argv", ["restore_db.py", str(backup_path)])
    monkeypatch.setattr("builtins.input", lambda _: "n")
    restore_module.main()

    # No safety backup should have been taken since the user declined.
    assert set(settings.backup_dir.glob("backup_*.tar.gz")) == backups_before
