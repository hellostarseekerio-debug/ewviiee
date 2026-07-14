"""Covers app/posters/corrections.py (the parser's self-improvement loop)
and its integration into app/posters/parser.py - a staff-taught district
correction for an estate the parser can resolve but can't place must be
remembered and applied automatically on every future parse mentioning
that same estate name."""
from __future__ import annotations

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.core.models import Base
from app.posters.corrections import lookup_correction, record_correction
from app.posters.parser import parse_block
from app.rules.engine import RuleEngine, load_ruleset
from app.core.config import get_settings


@pytest.fixture
def db() -> Session:
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    session = sessionmaker(bind=engine)()
    yield session
    session.close()


@pytest.fixture
def rule_engine():
    settings = get_settings()
    return RuleEngine(load_ruleset(settings.config_dir))


def test_record_and_lookup_roundtrip(db):
    record_correction(db, key_type="estate_name", key_value="未知苑", field="district", value="大埔", corrected_by="alice")
    assert lookup_correction(db, key_type="estate_name", key_value="未知苑", field="district") == "大埔"


def test_lookup_returns_none_when_no_correction_exists(db):
    assert lookup_correction(db, key_type="estate_name", key_value="沒有記錄", field="district") is None


def test_recording_again_replaces_the_previous_value(db):
    record_correction(db, key_type="estate_name", key_value="未知苑", field="district", value="大埔", corrected_by="alice")
    record_correction(db, key_type="estate_name", key_value="未知苑", field="district", value="沙田", corrected_by="bob")
    assert lookup_correction(db, key_type="estate_name", key_value="未知苑", field="district") == "沙田"


def test_parser_uses_learned_correction_for_an_unlisted_estate(db, rule_engine):
    text = "20260710-通告-40X-未知苑\nhttps://www.dropbox.com/s/aaa/f.pdf"

    before = parse_block(text, rule_engine, db=db)
    assert before.estate == "未知苑"
    assert before.district is None

    record_correction(db, key_type="estate_name", key_value=before.estate, field="district", value="大埔", corrected_by="alice")
    db.commit()

    after = parse_block(text, rule_engine, db=db)
    assert after.district == "大埔"
    assert after.field_sources["district"] == "learned"
    assert after.field_confidence["district"] == 1.0


def test_parser_without_db_session_ignores_learned_corrections(rule_engine):
    """No db session passed (e.g. a caller that hasn't wired it up) -
    the learned-correction lookup is simply skipped, not an error."""
    text = "20260710-通告-40X-陌生邨\nhttps://www.dropbox.com/s/bbb/f.pdf"
    parsed = parse_block(text, rule_engine, db=None)
    assert parsed.estate == "陌生邨"
    assert parsed.district is None
