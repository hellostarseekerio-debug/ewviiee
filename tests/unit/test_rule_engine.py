from __future__ import annotations

from datetime import datetime

from app.core.config import get_settings
from app.rules.engine import RuleEngine, load_ruleset


def _build_engine() -> RuleEngine:
    settings = get_settings()
    ruleset = load_ruleset(settings.config_dir)
    return RuleEngine(ruleset)


def test_resolve_district_by_alias():
    engine = _build_engine()
    district = engine.resolve_district("觀塘區申請表")
    assert district is not None
    assert district.id == "kwun_tong"


def test_resolve_estate_scoped_to_district():
    engine = _build_engine()
    district = engine.resolve_district("Kwun Tong")
    estate = engine.resolve_estate("藍田邨 poster v2", district_id=district.id)
    assert estate is not None
    assert estate.id == "lam_tin_estate"


def test_resolve_estate_no_match_returns_none():
    engine = _build_engine()
    estate = engine.resolve_estate("completely unrelated text", district_id="kwun_tong")
    assert estate is None


def test_validate_fields_reports_missing_required():
    engine = _build_engine()
    errors = engine.validate_fields({"district": "Kwun Tong"})
    assert any("estate" in e for e in errors)
    assert any("politician" in e for e in errors)


def test_validate_fields_passes_when_complete():
    engine = _build_engine()
    errors = engine.validate_fields(
        {
            "district": "Kwun Tong",
            "estate": "Lam Tin Estate",
            "politician": "Chan Tai Man",
            "title": "Housing Poster",
            "version": "2",
        }
    )
    assert errors == []


def test_build_output_name_uses_naming_pattern():
    engine = _build_engine()
    name = engine.build_output_name(
        {
            "district": "Kwun Tong",
            "estate": "Lam Tin Estate",
            "version": "2",
            "date": datetime(2026, 7, 11),
        }
    )
    assert name == "Kwun Tong_Lam Tin Estate_2_20260711.pdf"
