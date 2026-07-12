"""Covers app/posters/parser.py - the paste-text -> structured Poster
Archive record parser. Every extractor must degrade to None on
unrecognized input rather than raise, per the feature's explicit
requirement ("leave it blank instead of crashing")."""
from __future__ import annotations

import pytest

from app.core.config import get_settings
from app.posters.parser import parse_block, parse_poster_text, split_into_blocks
from app.rules.engine import RuleEngine, load_ruleset


@pytest.fixture
def rule_engine():
    settings = get_settings()
    return RuleEngine(load_ruleset(settings.config_dir))


SAMPLE_TEXT = """\
沙田 20260707-海報-好消息-73H-愉翠苑來往大埔富蝶邨
https://www.dropbox.com/scl/fo/abc123/example1?dl=0

【20260701-滬港兩地「跨境通辦」正式開通！】
https://www.dropbox.com/scl/fo/def456/example2
"""


def test_split_into_blocks_splits_on_blank_lines_after_a_link():
    blocks = split_into_blocks(SAMPLE_TEXT)
    assert len(blocks) == 2
    assert "abc123" in blocks[0]
    assert "def456" in blocks[1]


def test_split_into_blocks_on_empty_input_returns_nothing():
    assert split_into_blocks("") == []
    assert split_into_blocks("   \n\n   ") == []


def test_split_into_blocks_ignores_text_with_no_dropbox_link():
    assert split_into_blocks("just some text\nwith no link at all") == []


def test_parse_poster_text_extracts_district_route_date_and_type(rule_engine):
    results = parse_poster_text(SAMPLE_TEXT, rule_engine)
    assert len(results) == 2

    first = results[0]
    assert first.district == "Sha Tin"
    assert first.route_number == "73H"
    assert first.document_date.year == 2026
    assert first.document_date.month == 7
    assert first.document_date.day == 7
    assert first.poster_type == "poster"
    assert first.language == "zh"
    assert first.dropbox_url.startswith("https://www.dropbox.com/")
    assert first.warnings == []


def test_parse_poster_text_extracts_bracketed_title(rule_engine):
    results = parse_poster_text(SAMPLE_TEXT, rule_engine)
    second = results[1]
    assert second.poster_title == "20260701-滬港兩地「跨境通辦」正式開通！"
    assert second.document_date.month == 7
    assert second.document_date.day == 1


def test_parse_poster_text_never_raises_on_garbage_input(rule_engine):
    garbage_inputs = [
        "",
        "\n\n\n\n",
        "random text with no structure whatsoever",
        "https://www.dropbox.com/",  # link with nothing else
        "@@@###???!!!\nhttps://www.dropbox.com/x",
        "20991399 not a real date\nhttps://www.dropbox.com/y",  # invalid month/day
        "a" * 5000 + "\nhttps://www.dropbox.com/z",  # very long line
    ]
    for text in garbage_inputs:
        results = parse_poster_text(text, rule_engine)
        assert isinstance(results, list)  # must not raise, regardless of content


def test_parse_poster_text_without_rule_engine_still_works():
    """rule_engine is optional - district/estate simply stay None without
    it, everything else still extracts normally."""
    results = parse_poster_text(SAMPLE_TEXT, rule_engine=None)
    assert len(results) == 2
    assert results[0].district is None
    assert results[0].route_number == "73H"


def test_parse_poster_text_skips_blocks_without_a_dropbox_link(rule_engine):
    text = SAMPLE_TEXT + "\nAnother poster with no link at all\n"
    results = parse_poster_text(text, rule_engine)
    assert len(results) == 2  # the trailing linkless block is not included


def test_invalid_date_is_left_blank_not_raised(rule_engine):
    block = "20991399-bad-date\nhttps://www.dropbox.com/scl/fo/bad-date"
    parsed = parse_block(block, rule_engine)
    assert parsed is not None
    assert parsed.document_date is None


def test_multiple_records_produce_distinct_urls(rule_engine):
    results = parse_poster_text(SAMPLE_TEXT, rule_engine)
    urls = [r.dropbox_url for r in results]
    assert len(urls) == len(set(urls))


def test_keywords_are_extracted_and_deduplicated(rule_engine):
    results = parse_poster_text(SAMPLE_TEXT, rule_engine)
    assert isinstance(results[0].keywords, list)
    assert len(results[0].keywords) == len(set(results[0].keywords))


def test_english_only_text_detected_as_english(rule_engine):
    block = "Kwun Tong bus route notice\nhttps://www.dropbox.com/scl/fo/english-only"
    parsed = parse_block(block, rule_engine)
    assert parsed.language == "en"
