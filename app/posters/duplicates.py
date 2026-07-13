"""Duplicate detection for Poster Archive records - reuses
app/rules/fuzzy.py's `similarity()` (already built for district/estate
resolution) rather than a second string-matching engine.

Detects two independent kinds of duplicate:
  - exact Dropbox link reuse (already prevented by a DB UNIQUE constraint
    at write time - this module surfaces *existing* duplicates for
    review, which can only occur from data imported before that
    constraint existed, or a downgrade/restore path);
  - near-duplicate titles (fuzzy similarity above a threshold), which the
    UNIQUE constraint can't catch since two records can have genuinely
    different Dropbox links but the same or near-identical title (e.g.
    the same notice re-uploaded under a new link).

Deliberately does not attempt near-duplicate *file* detection (perceptual
hashing of the linked image/PDF) - that requires actually downloading
every candidate pair's file, which is a meaningfully larger, slower, and
riskier feature (network calls, image processing dependencies) than
comparing metadata already in the database. Flagged as follow-up work.
"""
from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy.orm import Session

from app.core.models import Poster
from app.rules.fuzzy import similarity

TITLE_SIMILARITY_THRESHOLD = 0.85


@dataclass
class DuplicateGroup:
    reason: str  # "exact_dropbox_link" | "similar_title"
    poster_ids: list[str]
    detail: str


def find_exact_link_duplicates(db: Session) -> list[DuplicateGroup]:
    """Groups of posters sharing the exact same (non-null) dropbox_url -
    should be empty in a healthy system (a DB UNIQUE constraint prevents
    new ones), but surfaced here in case older data predates it."""
    rows = (
        db.query(Poster.dropbox_url, Poster.id)
        .filter(Poster.dropbox_url.isnot(None))
        .order_by(Poster.dropbox_url)
        .all()
    )
    by_url: dict[str, list[str]] = {}
    for url, poster_id in rows:
        by_url.setdefault(url, []).append(poster_id)
    return [
        DuplicateGroup(reason="exact_dropbox_link", poster_ids=ids, detail=url)
        for url, ids in by_url.items()
        if len(ids) > 1
    ]


def find_similar_title_duplicates(
    db: Session, *, threshold: float = TITLE_SIMILARITY_THRESHOLD, limit: int = 500
) -> list[DuplicateGroup]:
    """Pairwise-compares titles among the `limit` most recent titled
    posters. O(n^2) similarity checks - fine at the `limit` default (500
    -> ~125k comparisons, each a cheap difflib ratio) but deliberately
    bounded rather than run over the whole archive at 50,000+ rows, where
    an unbounded pairwise scan would be the actual scaling hazard."""
    rows = (
        db.query(Poster.id, Poster.poster_title)
        .filter(Poster.poster_title.isnot(None))
        .order_by(Poster.created_at.desc())
        .limit(limit)
        .all()
    )
    groups: list[DuplicateGroup] = []
    seen: set[str] = set()
    for i, (id_a, title_a) in enumerate(rows):
        if id_a in seen or not title_a:
            continue
        matches = [id_a]
        for id_b, title_b in rows[i + 1 :]:
            if id_b in seen or not title_b:
                continue
            if similarity(title_a, title_b) >= threshold:
                matches.append(id_b)
        if len(matches) > 1:
            seen.update(matches)
            groups.append(DuplicateGroup(reason="similar_title", poster_ids=matches, detail=title_a))
    return groups


def find_all_duplicates(db: Session) -> list[DuplicateGroup]:
    return find_exact_link_duplicates(db) + find_similar_title_duplicates(db)
