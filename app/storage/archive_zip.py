"""Generic ZIP export builder. Not poster-specific in spirit (it only
depends on a small "exportable row" shape - see `ExportableRecord`), used
today for Poster Archive exports via app/api/routes/posters.py.

Produces one ZIP containing:
  - each record's file (fetched through DownloadService - the caller never
    knows whether that meant a local path or a Dropbox shared link),
    arranged under its folder's breadcrumb path so the ZIP's own directory
    structure mirrors the archive's;
  - metadata.csv, one row per requested record (including ones that had to
    be skipped, with a "skip_reason" column) so the export is still useful
    as a spreadsheet even when some files couldn't be fetched;
  - README.txt with the generation timestamp and a short summary.

One bad/expired Dropbox link must never sink an export of thousands of
good ones - every fetch failure is caught and recorded as a skip, not
raised.
"""
from __future__ import annotations

import csv
import io
import zipfile
from dataclasses import dataclass, field
from datetime import datetime

from app.core.models import Folder
from app.storage.download_service import DownloadService, StorageError


@dataclass
class ExportableRecord:
    """The minimal shape archive_zip needs from any resource row - callers
    build a list of these from Poster (or, later, Document) rows rather
    than this module importing a concrete model."""

    id: str
    title: str | None
    file_reference: str | None  # a Dropbox URL or local path; None if nothing to fetch
    folder_id: str | None
    metadata: dict[str, str] = field(default_factory=dict)


@dataclass
class ZipExportResult:
    buffer: bytes
    total_requested: int
    included: int
    skipped: list[dict[str, str]]


class ZipExportLimitError(ValueError):
    """Raised when a request exceeds a configured export limit (file count
    or total bytes) - callers turn this into an HTTP 413/400, not a
    partial/truncated export that would silently drop records."""


def _safe_segment(name: str) -> str:
    cleaned = "".join(c for c in name if c not in '\\/:*?"<>|').strip()
    return cleaned or "unnamed"


def _folder_arc_prefix(record_folder_id: str | None, folders_by_id: dict[str, Folder]) -> str:
    if not record_folder_id or record_folder_id not in folders_by_id:
        return "Unfiled"
    folder = folders_by_id[record_folder_id]
    ancestor_ids = folder.path.split("/")
    names = [folders_by_id[i].name for i in ancestor_ids if i in folders_by_id]
    return "/".join(_safe_segment(n) for n in names) or "Unfiled"


def build_zip_export(
    db,
    records: list[ExportableRecord],
    *,
    download_service: DownloadService,
    max_files: int,
    max_total_bytes: int,
    archive_label: str = "Archive",
) -> ZipExportResult:
    if len(records) > max_files:
        raise ZipExportLimitError(f"Export exceeds the {max_files}-file limit ({len(records)} requested)")

    folders_by_id = {f.id: f for f in db.query(Folder).all()}
    buffer = io.BytesIO()
    included = 0
    total_bytes = 0
    skipped: list[dict[str, str]] = []
    metadata_rows: list[dict[str, str]] = []
    used_arcnames: set[str] = set()

    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as zf:
        for record in records:
            prefix = _folder_arc_prefix(record.folder_id, folders_by_id)
            row = {"id": record.id, "title": record.title or "", "folder": prefix, "skip_reason": "", **record.metadata}

            if not record.file_reference:
                row["skip_reason"] = "No file reference on this record"
                skipped.append({"id": record.id, "reason": row["skip_reason"]})
                metadata_rows.append(row)
                continue

            try:
                obj = download_service.fetch(record.file_reference)
            except StorageError as exc:
                row["skip_reason"] = str(exc)
                skipped.append({"id": record.id, "reason": str(exc)})
                metadata_rows.append(row)
                continue

            if total_bytes + (obj.size_bytes or 0) > max_total_bytes:
                row["skip_reason"] = "Export size limit reached"
                skipped.append({"id": record.id, "reason": row["skip_reason"]})
                metadata_rows.append(row)
                continue

            total_bytes += obj.size_bytes or 0
            base = f"{prefix}/{_safe_segment(record.title or record.id)}_{record.id[:8]}_{_safe_segment(obj.name)}"
            arcname = base
            suffix = 1
            while arcname in used_arcnames:
                arcname = f"{base}.{suffix}"
                suffix += 1
            used_arcnames.add(arcname)

            zf.writestr(arcname, obj.content)
            included += 1
            metadata_rows.append(row)

        zf.writestr("metadata.csv", _build_metadata_csv(metadata_rows))
        zf.writestr("README.txt", _build_readme(archive_label, len(records), included, skipped))

    return ZipExportResult(
        buffer=buffer.getvalue(), total_requested=len(records), included=included, skipped=skipped
    )


def _build_metadata_csv(rows: list[dict[str, str]]) -> str:
    if not rows:
        return ""
    fieldnames: list[str] = []
    for row in rows:
        for key in row:
            if key not in fieldnames:
                fieldnames.append(key)
    out = io.StringIO()
    writer = csv.DictWriter(out, fieldnames=fieldnames)
    writer.writeheader()
    writer.writerows(rows)
    return out.getvalue()


def _build_readme(archive_label: str, total_requested: int, included: int, skipped: list[dict[str, str]]) -> str:
    lines = [
        f"{archive_label} export",
        f"Generated: {datetime.utcnow().isoformat()}Z",
        f"Records requested: {total_requested}",
        f"Files included: {included}",
        f"Records skipped: {len(skipped)}",
    ]
    if skipped:
        lines.append("")
        lines.append("Skipped records (see metadata.csv for full details):")
        for entry in skipped[:50]:
            lines.append(f"  - {entry['id']}: {entry['reason']}")
        if len(skipped) > 50:
            lines.append(f"  ... and {len(skipped) - 50} more (see metadata.csv)")
    return "\n".join(lines) + "\n"
