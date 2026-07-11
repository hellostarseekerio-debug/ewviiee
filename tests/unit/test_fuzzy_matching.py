"""Tests for the fuzzy matching tier added between exact alias matching and
the AI fallback in the rule engine. These lock in two real bugs found
during development:
  1. naive substring matching was order-dependent and picked the *first*
     candidate that matched rather than the *best* one, causing
     "Lam Tin Estate" text to sometimes resolve to the "Sha Tin" district;
  2. short Latin abbreviations like "ST"/"KT" trivially substring-matched
     inside unrelated English words (e.g. "ST" inside "estate").
"""
from __future__ import annotations

from app.rules.fuzzy import best_match, contains_cjk, similarity


def test_exact_substring_match_scores_1():
    assert similarity("Kwun Tong", "觀塘 Kwun Tong district") == 1.0


def test_short_latin_alias_does_not_match_inside_unrelated_word():
    # "ST" must not match just because it's a substring of "estate".
    assert similarity("ST", "lam tin estate application") < 1.0


def test_short_latin_alias_matches_as_whole_word():
    assert similarity("ST", "ST office memo") == 1.0


def test_short_cjk_alias_matches_via_containment():
    # Chinese 2-character names are specific enough that plain containment
    # is safe and expected to work, unlike 2-letter Latin abbreviations.
    assert similarity("觀塘", "觀塘區申請表") == 1.0


def test_typo_tolerance_via_fuzzy_ratio():
    score = similarity("Kwun Tong", "Kwun Toung district office")
    assert 0.7 < score < 1.0


def test_unrelated_text_scores_below_match_threshold():
    # Below DEFAULT_THRESHOLD (0.72) is what actually matters - best_match
    # will not resolve it, regardless of the exact raw ratio.
    assert similarity("Kwun Tong", "completely unrelated text about nothing") < 0.72


def test_contains_cjk_detects_chinese_characters():
    assert contains_cjk("觀塘")
    assert not contains_cjk("Kwun Tong")


def test_best_match_picks_highest_scoring_candidate_not_first():
    # "Lam Tin Estate" text should resolve to Lam Tin, not to Sha Tin, even
    # though naive substring matching on the short "Tin" fragment used to
    # pick whichever candidate happened to be checked first.
    candidates = [
        ("sha_tin", ["Sha Tin", "沙田", "ST"]),
        ("lam_tin", ["Lam Tin Estate", "藍田邨"]),
    ]
    result = best_match("藍田邨 Lam Tin Estate", candidates)
    assert result is not None
    assert result.entry == "lam_tin"
    assert result.confidence == 1.0


def test_best_match_returns_none_below_threshold():
    candidates = [("kwun_tong", ["Kwun Tong", "觀塘"])]
    result = best_match("nothing related here at all", candidates)
    assert result is None


def test_best_match_returns_none_for_ambiguous_short_alias_collision():
    # Regression test for the exact bug found in manual testing: a
    # filename like "lam_tin_estate_application" must not resolve to
    # Sha Tin purely because "ST" is a substring of "estate".
    candidates = [
        ("sha_tin", ["Sha Tin", "沙田", "ST"]),
        ("kwun_tong", ["Kwun Tong", "觀塘", "KT"]),
    ]
    result = best_match("lam_tin_estate_application", candidates)
    assert result is None
