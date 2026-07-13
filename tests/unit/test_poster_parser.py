"""Covers app/posters/parser.py - the paste-text -> structured Poster
Archive record parser. Every extractor must degrade to None on
unrecognized input rather than raise, per the feature's explicit
requirement ("leave it blank instead of crashing")."""
from __future__ import annotations

import pytest

from app.core.config import get_settings
from app.posters.parser import (
    _extract_government_department,
    _extract_route,
    _extract_title,
    _extract_version,
    parse_block,
    parse_poster_text,
    split_into_blocks,
)
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


# ---------------------------------------------------------------------------
# Real reported example: "沙田 20260707-海報-好消息-73H-愉翠苑來往大埔富蝶邨"
# followed by a Dropbox link. Covers every field the bug report called out
# as broken: title, district, estate, route, date, poster type.
# ---------------------------------------------------------------------------

REAL_EXAMPLE_TEXT = (
    "沙田 20260707-海報-好消息-73H-愉翠苑來往大埔富蝶邨\n"
    "https://www.dropbox.com/scl/fi/abc123/poster.pdf?rlkey=xyz&dl=0\n"
)


def test_real_example_extracts_every_field(rule_engine):
    results = parse_poster_text(REAL_EXAMPLE_TEXT, rule_engine)
    assert len(results) == 1
    poster = results[0]

    assert poster.poster_title == "20260707-海報-好消息-73H-愉翠苑來往大埔富蝶邨"
    assert poster.district == "Sha Tin"  # canonical name for 沙田, matching every other district field in the app
    assert poster.estate == "愉翠苑"
    assert poster.route_number == "73H"
    assert poster.document_date.year == 2026
    assert poster.document_date.month == 7
    assert poster.document_date.day == 7
    assert poster.poster_type == "poster"
    assert poster.dropbox_url.startswith("https://www.dropbox.com/")


def test_real_example_title_never_untitled_when_metadata_exists(rule_engine):
    results = parse_poster_text(REAL_EXAMPLE_TEXT, rule_engine)
    assert results[0].poster_title is not None
    assert results[0].poster_title != "(untitled)"


def test_only_dropbox_url_with_no_preceding_line_has_no_title(rule_engine):
    """The one legitimate case for a missing title: a link with no
    metadata line in front of it at all (nothing else to extract)."""
    block = "https://www.dropbox.com/scl/fi/onlylink/poster.pdf?dl=0"
    parsed = parse_block(block, rule_engine)
    assert parsed is not None
    assert parsed.poster_title is None
    assert parsed.district is None
    assert parsed.estate is None
    assert parsed.route_number is None
    assert parsed.document_date is None


def test_title_strips_leading_district_but_keeps_estate_and_route(rule_engine):
    """District is stripped from the front of the title since it's a
    separate structured field, but the estate/route/date/poster-type text
    embedded further into the title string is left intact."""
    poster = parse_poster_text(REAL_EXAMPLE_TEXT, rule_engine)[0]
    assert not poster.poster_title.startswith("沙田")
    assert "愉翠苑" in poster.poster_title
    assert "73H" in poster.poster_title


def test_estate_not_in_config_still_resolved_via_suffix_fallback(rule_engine):
    """愉翠苑 is deliberately not present in config/rules/estates.yaml -
    this is exactly the "missing field" case the parser must recover from
    without needing config changes or an AI provider."""
    poster = parse_poster_text(REAL_EXAMPLE_TEXT, rule_engine)[0]
    assert poster.estate == "愉翠苑"


def test_survives_invisible_zero_width_separator_line(rule_engine):
    """A 'blank' line between two records that actually carries a
    zero-width space (common after copy-pasting from web pages/Notion/
    Word) used to make str.strip() see it as non-empty, causing both
    records to be merged into a single block and losing the association
    between the second record's metadata and its own Dropbox link."""
    text = (
        "沙田 20260707-海報-好消息-73H-愉翠苑來往大埔富蝶邨\n"
        "https://www.dropbox.com/scl/fi/abc123/poster1.pdf?dl=0\n"
        "​\n"  # zero-width space masquerading as a blank line
        "觀塘 20260710-通告-290A-彩虹邨\n"
        "https://www.dropbox.com/scl/fi/def456/poster2.pdf?dl=0\n"
    )
    results = parse_poster_text(text, rule_engine)
    assert len(results) == 2
    assert results[0].dropbox_url.endswith("poster1.pdf?dl=0")
    assert results[0].district == "Sha Tin"
    assert results[0].estate == "愉翠苑"
    assert results[1].dropbox_url.endswith("poster2.pdf?dl=0")
    assert results[1].district == "Kwun Tong"
    assert results[1].estate == "Choi Hung Estate"
    assert results[1].route_number == "290A"


def test_survives_inconsistent_spacing_and_blank_line_runs(rule_engine):
    """Extra blank lines between the metadata line and its URL, and extra
    leading/trailing whitespace on both, must not break association."""
    text = (
        "  沙田   20260707-海報-好消息-73H-愉翠苑來往大埔富蝶邨   \n"
        "\n\n\n"
        "   https://www.dropbox.com/scl/fi/abc123/poster.pdf?dl=0  \n"
    )
    results = parse_poster_text(text, rule_engine)
    assert len(results) == 1
    assert results[0].district == "Sha Tin"
    assert results[0].estate == "愉翠苑"
    assert results[0].dropbox_url == "https://www.dropbox.com/scl/fi/abc123/poster.pdf?dl=0"


def test_survives_chinese_punctuation_in_metadata_line(rule_engine):
    block = (
        "沙田，好消息！73H：愉翠苑（來往大埔富蝶邨）\n"
        "https://www.dropbox.com/scl/fi/punctuated/poster.pdf?dl=0"
    )
    parsed = parse_block(block, rule_engine)
    assert parsed is not None
    assert parsed.district == "Sha Tin"
    assert parsed.route_number == "73H"
    assert parsed.poster_title is not None
    assert parsed.poster_title != "(untitled)"


def test_closest_preceding_line_wins_over_earlier_stray_text(rule_engine):
    """Per the "associate with the closest preceding non-empty line"
    requirement: unrelated text further back (e.g. a leftover heading from
    a previous paste, or explanatory notes) must never be pulled into the
    next record's metadata - only the line immediately before the link is
    used."""
    text = (
        "some unrelated heading that is not a record\n"
        "沙田 20260707-海報-好消息-73H-愉翠苑來往大埔富蝶邨\n"
        "https://www.dropbox.com/scl/fi/abc123/poster.pdf?dl=0\n"
    )
    results = parse_poster_text(text, rule_engine)
    assert len(results) == 1
    assert "unrelated heading" not in results[0].poster_title
    assert results[0].district == "Sha Tin"


def test_three_records_back_to_back_all_associate_correctly(rule_engine):
    text = (
        "沙田 20260707-海報-好消息-73H-愉翠苑來往大埔富蝶邨\n"
        "https://www.dropbox.com/scl/fi/one/poster.pdf?dl=0\n"
        "觀塘 20260710-通告-290A-彩虹邨\n"
        "https://www.dropbox.com/scl/fi/two/poster.pdf?dl=0\n"
        "黃大仙 20260712-公告-慈雲山邨\n"
        "https://www.dropbox.com/scl/fi/three/poster.pdf?dl=0\n"
    )
    results = parse_poster_text(text, rule_engine)
    assert len(results) == 3
    assert [r.dropbox_url.split("/")[-2] for r in results] == ["one", "two", "three"]
    assert results[0].district == "Sha Tin"
    assert results[1].district == "Kwun Tong"
    assert results[2].district == "Wong Tai Sin"


# ---------------------------------------------------------------------------
# Phase 2B: parser bug fixes (garbage route/title values) and new fields
# (version, government department, needs_review confidence flagging).
# ---------------------------------------------------------------------------


def test_bare_single_digit_route_is_rejected_as_noise():
    """The real-world false positive this guards against: a version marker
    like "版 2" tokenizing as a standalone route "2" once whitespace
    separates the digit from its prefix."""
    assert _extract_route("好消息 版 2 沙田") is None


def test_two_digit_or_lettered_routes_still_extracted():
    assert _extract_route("73H 巴士路線") == "73H"
    assert _extract_route("路線 12 開出") == "12"


def test_title_that_is_only_punctuation_returns_none_not_a_dash():
    assert _extract_title("-") is None
    assert _extract_title("- - -") is None
    assert _extract_title("   ") is None


def test_title_with_real_content_is_not_affected_by_punctuation_fix():
    assert _extract_title("20260707-海報-好消息") == "20260707-海報-好消息"


def test_extract_version_v_prefix():
    assert _extract_version("housing_notice_v2.pdf") == "2"
    assert _extract_version("Notice V2.1 final") == "2.1"


def test_extract_version_chinese_forms():
    assert _extract_version("屋邨通告第2版") == "2"
    assert _extract_version("屋邨通告 版3") == "3"


def test_extract_version_absent_returns_none():
    assert _extract_version("no version marker here") is None


def test_extract_government_department():
    assert _extract_government_department("運輸署交通通告") == "運輸署"
    assert _extract_government_department("房屋署屋邨通告") == "房屋署"
    assert _extract_government_department("no department mentioned") is None


def test_needs_review_flagged_when_nothing_identifying_resolved(rule_engine):
    """A block whose metadata line is pure noise (no district, no estate,
    no usable title) must be flagged for manual review rather than
    silently stored as if it were confidently parsed."""
    block = "@@@ ### !!! \nhttps://www.dropbox.com/scl/fi/noise/poster.pdf?dl=0"
    parsed = parse_block(block, rule_engine)
    assert parsed is not None
    assert parsed.needs_review is True


def test_needs_review_false_when_district_resolved(rule_engine):
    parsed = parse_block(
        "沙田 20260707-海報-好消息-73H-愉翠苑\nhttps://www.dropbox.com/scl/fi/good/poster.pdf?dl=0",
        rule_engine,
    )
    assert parsed is not None
    assert parsed.needs_review is False


def test_transport_and_housing_notice_poster_types(rule_engine):
    transport = parse_block(
        "沙田 交通通告 73H\nhttps://www.dropbox.com/scl/fi/transport/poster.pdf?dl=0", rule_engine
    )
    housing = parse_block(
        "沙田 房屋通告 愉翠苑\nhttps://www.dropbox.com/scl/fi/housing/poster.pdf?dl=0", rule_engine
    )
    assert transport is not None and transport.poster_type == "transport_notice"
    assert housing is not None and housing.poster_type == "housing_notice"
