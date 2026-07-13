"""Covers app/posters/estates.py's EstateMetadataService - the "resolve
once, get district/region/politicians/dropbox-folder/templates back for
free" wrapper over RuleEngine used by the redesigned metadata extraction
pipeline (app/posters/parser.py)."""
from __future__ import annotations

import pytest

from app.core.config import get_settings
from app.posters.estates import EstateMetadataService
from app.rules.engine import RuleEngine, load_ruleset


@pytest.fixture
def service():
    settings = get_settings()
    engine = RuleEngine(load_ruleset(settings.config_dir))
    return EstateMetadataService(engine)


def test_resolve_returns_full_metadata_bundle(service):
    meta = service.resolve("愉翠苑一帶")
    assert meta is not None
    assert meta.estate_name == "愉翠苑"
    assert meta.district_id == "sha_tin"
    assert meta.district_name == "沙田"
    assert meta.region == "New Territories"


def test_resolve_returns_none_for_unrecognized_text(service):
    assert service.resolve("完全無關嘅內容") is None


def test_resolve_respects_district_id_filter(service):
    # 彩虹邨 is Kwun Tong, not Sha Tin - filtering by the wrong district
    # must not match it via cross-district fuzzy matching.
    assert service.resolve("彩虹邨", district_id="sha_tin") is None
    assert service.resolve("彩虹邨", district_id="kwun_tong") is not None


def test_region_for_district(service):
    assert service.region_for_district("sha_tin") == "New Territories"
    assert service.region_for_district("central_western") == "Hong Kong Island"
    assert service.region_for_district("kwun_tong") == "Kowloon"


def test_native_district_name(service):
    assert service.native_district_name("sha_tin") == "沙田"
    assert service.native_district_name("nonexistent_id") is None


def test_common_routes_politicians_and_templates_default_to_empty(service):
    """No estate in config/rules/estates.yaml has these populated yet
    (deliberately left for office staff to fill in - see the YAML file's
    header comment) - the service must still return well-typed empty
    values, never None/crash, for an estate that resolves but has no
    metadata beyond its name/district."""
    meta = service.resolve("愉翠苑")
    assert meta.common_routes == []
    assert meta.politicians == []
    assert meta.poster_templates == []
    assert meta.dropbox_folder is None
