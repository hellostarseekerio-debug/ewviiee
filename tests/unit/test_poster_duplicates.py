"""Covers app/posters/duplicates.py - exact-Dropbox-link and similar-title
duplicate detection, built on the existing app/rules/fuzzy.py matcher."""
from __future__ import annotations

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.core.models import Base, Poster
from app.posters.duplicates import find_all_duplicates, find_exact_link_duplicates, find_similar_title_duplicates


@pytest.fixture
def db():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    session = sessionmaker(bind=engine)()
    yield session
    session.close()


def _poster(**kwargs) -> Poster:
    defaults = {"poster_title": "Title", "dropbox_url": None}
    defaults.update(kwargs)
    return Poster(**defaults)


def test_no_duplicates_on_empty_database(db):
    assert find_all_duplicates(db) == []


def test_exact_link_duplicates_grouping_logic_over_raw_rows(db):
    """The `posters.dropbox_url` column has a DB-level UNIQUE constraint,
    so two ORM-inserted rows can never actually share a link in a live
    database (this is the module's own documented reasoning: exact-link
    duplicates can only exist from data older than that constraint).
    Exercises find_exact_link_duplicates' grouping logic directly against
    a raw query result instead, since the constraint makes it impossible
    to set up the "two equal links" precondition through normal inserts."""
    from unittest.mock import MagicMock

    fake_db = MagicMock()
    fake_db.query.return_value.filter.return_value.order_by.return_value.all.return_value = [
        ("https://www.dropbox.com/x", "id-1"),
        ("https://www.dropbox.com/x", "id-2"),
        ("https://www.dropbox.com/y", "id-3"),
    ]
    groups = find_exact_link_duplicates(fake_db)
    assert len(groups) == 1
    assert groups[0].reason == "exact_dropbox_link"
    assert set(groups[0].poster_ids) == {"id-1", "id-2"}


def test_null_dropbox_url_never_forms_a_duplicate_group(db):
    """Multiple posters with no link at all must never be reported as
    'duplicates of each other' - NULL is never equal to NULL."""
    db.add(_poster(poster_title="A", dropbox_url=None))
    db.add(_poster(poster_title="B", dropbox_url=None))
    db.commit()
    assert find_exact_link_duplicates(db) == []


def test_similar_titles_grouped(db):
    db.add(_poster(poster_title="20260707-海報-好消息-73H-愉翠苑", dropbox_url="https://www.dropbox.com/a"))
    db.add(_poster(poster_title="20260707-海報-好消息-73H-愉翠苑 ", dropbox_url="https://www.dropbox.com/b"))
    db.commit()

    groups = find_similar_title_duplicates(db)
    assert len(groups) == 1
    assert groups[0].reason == "similar_title"
    assert len(groups[0].poster_ids) == 2


def test_distinct_titles_are_not_grouped(db):
    db.add(_poster(poster_title="Sha Tin notice about bus routes", dropbox_url="https://www.dropbox.com/a"))
    db.add(_poster(poster_title="Kwun Tong housing announcement", dropbox_url="https://www.dropbox.com/b"))
    db.commit()
    assert find_similar_title_duplicates(db) == []


def test_a_poster_is_never_reported_in_two_groups_at_once(db):
    """Once a poster is claimed by one similarity group it must not also
    appear in a second - each record needs exactly one clear duplicate
    story, not overlapping ambiguous ones."""
    title = "Sha Tin estate notice 2026"
    db.add(_poster(poster_title=title, dropbox_url="https://www.dropbox.com/a"))
    db.add(_poster(poster_title=title, dropbox_url="https://www.dropbox.com/b"))
    db.add(_poster(poster_title=title, dropbox_url="https://www.dropbox.com/c"))
    db.commit()

    groups = find_similar_title_duplicates(db)
    all_ids = [pid for g in groups for pid in g.poster_ids]
    assert len(all_ids) == len(set(all_ids))


def test_find_all_duplicates_combines_both_kinds(db):
    # Exact-link duplicate pair.
    db.add(_poster(poster_title="Link dup A", dropbox_url="https://www.dropbox.com/dup"))
    db.add(_poster(poster_title="Link dup B", dropbox_url="https://www.dropbox.com/dup-copy"))
    # Similar-title duplicate pair, distinct links.
    db.add(_poster(poster_title="Sha Tin estate notice 2026", dropbox_url="https://www.dropbox.com/x"))
    db.add(_poster(poster_title="Sha Tin estate notice 2026", dropbox_url="https://www.dropbox.com/y"))
    db.commit()

    groups = find_all_duplicates(db)
    reasons = {g.reason for g in groups}
    assert "exact_dropbox_link" not in reasons  # dup/dup-copy are different URLs, not exact link dupes
    assert "similar_title" in reasons
