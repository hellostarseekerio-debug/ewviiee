"""Covers app/storage/archive_zip.py - the generic ZIP export builder.
Uses a fake DownloadService (no real network/local file access) so these
tests exercise the builder's own logic: folder-hierarchy arcnames,
metadata.csv/README.txt content, per-record skip handling, and limits."""
from __future__ import annotations

import io
import zipfile

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.core.models import Base
from app.folders.service import create_folder
from app.storage.archive_zip import ExportableRecord, ZipExportLimitError, build_zip_export
from app.storage.providers.base import StorageError, StorageObject


@pytest.fixture
def db():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    session = sessionmaker(bind=engine)()
    yield session
    session.close()


class FakeDownloadService:
    def __init__(self, files: dict[str, StorageObject | Exception]):
        self._files = files

    def fetch(self, reference):
        result = self._files.get(reference)
        if isinstance(result, Exception):
            raise result
        if result is None:
            raise StorageError(f"no fixture for {reference}")
        return result


def _zip_names(buffer: bytes) -> list[str]:
    with zipfile.ZipFile(io.BytesIO(buffer)) as zf:
        return zf.namelist()


def test_build_zip_includes_metadata_csv_and_readme(db):
    records = [ExportableRecord(id="1", title="Poster A", file_reference=None, folder_id=None)]
    result = build_zip_export(
        db, records, download_service=FakeDownloadService({}), max_files=10, max_total_bytes=10_000
    )
    names = _zip_names(result.buffer)
    assert "metadata.csv" in names
    assert "README.txt" in names


def test_build_zip_places_file_under_folder_breadcrumb_path(db):
    root = create_folder(db, name="Poster Archive", parent_id=None, created_by="admin")
    year = create_folder(db, name="2026", parent_id=root.id, created_by="admin")
    obj = StorageObject(name="poster.pdf", size_bytes=5, content=b"hello")
    records = [ExportableRecord(id="1", title="Poster A", file_reference="ref-1", folder_id=year.id)]

    result = build_zip_export(
        db, records, download_service=FakeDownloadService({"ref-1": obj}), max_files=10, max_total_bytes=10_000
    )
    names = _zip_names(result.buffer)
    matching = [n for n in names if n.startswith("Poster Archive/2026/")]
    assert len(matching) == 1
    assert result.included == 1


def test_unfiled_record_lands_under_unfiled_prefix(db):
    obj = StorageObject(name="poster.pdf", size_bytes=5, content=b"hello")
    records = [ExportableRecord(id="1", title="Poster A", file_reference="ref-1", folder_id=None)]
    result = build_zip_export(
        db, records, download_service=FakeDownloadService({"ref-1": obj}), max_files=10, max_total_bytes=10_000
    )
    names = _zip_names(result.buffer)
    assert any(n.startswith("Unfiled/") for n in names)


def test_record_with_no_file_reference_is_skipped_not_raised(db):
    records = [ExportableRecord(id="1", title="No file", file_reference=None, folder_id=None)]
    result = build_zip_export(
        db, records, download_service=FakeDownloadService({}), max_files=10, max_total_bytes=10_000
    )
    assert result.included == 0
    assert len(result.skipped) == 1
    assert result.skipped[0]["id"] == "1"


def test_one_bad_link_does_not_sink_the_whole_export(db):
    good = StorageObject(name="good.pdf", size_bytes=3, content=b"abc")
    records = [
        ExportableRecord(id="1", title="Bad", file_reference="bad-ref", folder_id=None),
        ExportableRecord(id="2", title="Good", file_reference="good-ref", folder_id=None),
    ]
    service = FakeDownloadService({"bad-ref": StorageError("expired link"), "good-ref": good})
    result = build_zip_export(db, records, download_service=service, max_files=10, max_total_bytes=10_000)
    assert result.included == 1
    assert len(result.skipped) == 1
    assert result.skipped[0]["id"] == "1"
    assert "expired link" in result.skipped[0]["reason"]


def test_total_requested_matches_input_length_regardless_of_skips(db):
    records = [
        ExportableRecord(id=str(i), title=f"T{i}", file_reference=None, folder_id=None) for i in range(5)
    ]
    result = build_zip_export(
        db, records, download_service=FakeDownloadService({}), max_files=10, max_total_bytes=10_000
    )
    assert result.total_requested == 5


def test_exceeding_max_files_raises_limit_error(db):
    records = [ExportableRecord(id=str(i), title="X", file_reference=None, folder_id=None) for i in range(3)]
    with pytest.raises(ZipExportLimitError):
        build_zip_export(db, records, download_service=FakeDownloadService({}), max_files=2, max_total_bytes=10_000)


def test_exceeding_total_bytes_skips_remaining_records(db):
    big = StorageObject(name="big.bin", size_bytes=100, content=b"x" * 100)
    records = [
        ExportableRecord(id="1", title="First", file_reference="ref-1", folder_id=None),
        ExportableRecord(id="2", title="Second", file_reference="ref-2", folder_id=None),
    ]
    service = FakeDownloadService({"ref-1": big, "ref-2": big})
    result = build_zip_export(db, records, download_service=service, max_files=10, max_total_bytes=150)
    assert result.included == 1
    assert len(result.skipped) == 1
    assert "size limit" in result.skipped[0]["reason"]


def test_duplicate_arcnames_get_disambiguated(db):
    obj = StorageObject(name="poster.pdf", size_bytes=1, content=b"x")
    records = [
        ExportableRecord(id="1", title="Same Title", file_reference="ref-1", folder_id=None),
        ExportableRecord(id="2", title="Same Title", file_reference="ref-2", folder_id=None),
    ]
    # Same title but different ids - the id prefix already disambiguates in
    # practice, but this guards the fallback path if it ever doesn't.
    service = FakeDownloadService({"ref-1": obj, "ref-2": obj})
    result = build_zip_export(db, records, download_service=service, max_files=10, max_total_bytes=10_000)
    assert result.included == 2


def test_metadata_csv_has_a_row_per_requested_record_including_skipped(db):
    records = [
        ExportableRecord(id="1", title="Has file", file_reference="ref-1", folder_id=None),
        ExportableRecord(id="2", title="No file", file_reference=None, folder_id=None),
    ]
    obj = StorageObject(name="a.pdf", size_bytes=1, content=b"x")
    result = build_zip_export(
        db, records, download_service=FakeDownloadService({"ref-1": obj}), max_files=10, max_total_bytes=10_000
    )
    with zipfile.ZipFile(io.BytesIO(result.buffer)) as zf:
        csv_text = zf.read("metadata.csv").decode()
    assert "Has file" in csv_text
    assert "No file" in csv_text
