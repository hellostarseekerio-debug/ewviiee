"""Automatic Year -> Month -> District -> Estate folder suggestion for
imported/created posters (Phase 2 item #2). Missing segments (an
unresolved district/estate, or an unimportable folder name) degrade to an
explicit "Unfiled ..." placeholder segment rather than silently skipping
the record's filing altogether or crashing the import.

This is intentionally the *only* place that knows what "the poster
auto-filing scheme" means - app/api/routes/posters.py just calls
`resolve_or_create_poster_folder`, so the scheme can change later (e.g.
per-office configuration) without touching the route.
"""
from __future__ import annotations

from datetime import datetime

from sqlalchemy.orm import Session

from app.core.models import Folder
from app.folders.service import create_folder, list_children

ROOT_FOLDER_NAME = "Poster Archive"


def suggest_poster_path_segments(
    *, district: str | None, estate: str | None, document_date: datetime | None
) -> list[str]:
    """Ordered path segments under the shared root: Year -> Month ->
    District -> Estate. Uses today's date when no document_date was
    extracted, rather than leaving the record undated in the tree."""
    date = document_date or datetime.utcnow()
    return [
        str(date.year),
        date.strftime("%m - %B"),
        (district or "Unfiled district").strip(),
        (estate or "Unfiled estate").strip(),
    ]


def _get_or_create_child(db: Session, parent_id: str | None, name: str, created_by: str | None) -> Folder:
    existing = next(
        (f for f in list_children(db, parent_id) if f.name.strip().lower() == name.strip().lower()), None
    )
    if existing is not None:
        return existing
    return create_folder(db, name=name, parent_id=parent_id, created_by=created_by)


def get_or_create_path(db: Session, segments: list[str], *, created_by: str | None) -> Folder:
    """Finds-or-creates each segment in order under the shared
    ROOT_FOLDER_NAME folder, returning the deepest (final) folder. All
    auto-filed posters share one root so they land in one predictable
    place in the tree instead of scattering unrelated top-level folders."""
    folder = _get_or_create_child(db, None, ROOT_FOLDER_NAME, created_by)
    for name in segments:
        folder = _get_or_create_child(db, folder.id, name, created_by)
    return folder


def resolve_or_create_poster_folder(
    db: Session,
    *,
    folder_id_override: str | None,
    district: str | None,
    estate: str | None,
    document_date: datetime | None,
    created_by: str | None,
) -> str | None:
    """The single entry point app/api/routes/posters.py calls on
    create/import. An explicit `folder_id_override` (the user picking a
    destination themselves) always wins over the automatic suggestion -
    per the requirement that auto-filing is a default, not a mandate."""
    if folder_id_override:
        return folder_id_override
    segments = suggest_poster_path_segments(district=district, estate=estate, document_date=document_date)
    folder = get_or_create_path(db, segments, created_by=created_by)
    return folder.id
