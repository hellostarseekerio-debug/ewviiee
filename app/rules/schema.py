"""Typed views over the YAML rule configuration.

Nothing about districts, estates, politicians, or naming conventions is
hardcoded in Python - everything is loaded from config/rules/*.yaml so
office staff (or an admin) can update mappings without a code change or
redeploy.
"""
from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class District:
    id: str
    name: str
    aliases: list[str] = field(default_factory=list)
    # Hong Kong Island / Kowloon / New Territories - optional since not
    # every deployment needs it, but populated for all 18 districts
    # shipped in config/rules/districts.yaml.
    region: str | None = None

    @property
    def native_name(self) -> str:
        """The Chinese display name - the first CJK-containing alias, or
        `name` itself if none of its aliases contain CJK text. Kept as a
        derived property (not a separate YAML field) so existing entries
        need no edits: `name` stays the stable English identifier every
        other part of the codebase already reads, while parser-facing
        output can show the office's actual working language without a
        second name column to keep in sync."""
        for alias in self.aliases:
            if _has_cjk(alias):
                return alias
        return self.name


@dataclass
class Estate:
    id: str
    name: str
    district_id: str
    aliases: list[str] = field(default_factory=list)
    # The following are all optional/best-effort "estate metadata" (see
    # app/posters/estates.py's EstateMetadataService) - seed data only for
    # the handful of estates it's populated for today, meant to be filled
    # in by office staff over time via YAML edits, not a claim of
    # completeness.
    common_routes: list[str] = field(default_factory=list)
    politicians: list[str] = field(default_factory=list)
    dropbox_folder: str | None = None
    poster_templates: list[str] = field(default_factory=list)

    @property
    def native_name(self) -> str:
        for alias in self.aliases:
            if _has_cjk(alias):
                return alias
        return self.name


def _has_cjk(text: str) -> bool:
    return any("一" <= ch <= "鿿" for ch in text)


@dataclass
class ValidationRule:
    field: str
    required: bool = True
    pattern: str | None = None
    min_length: int | None = None
    max_length: int | None = None


@dataclass
class NamingRule:
    pattern: str  # e.g. "{district}_{estate}_{version}_{date}"
    date_format: str = "%Y%m%d"


@dataclass
class RuleSet:
    districts: list[District] = field(default_factory=list)
    estates: list[Estate] = field(default_factory=list)
    aliases: dict[str, str] = field(default_factory=dict)
    page_mappings: dict[str, int] = field(default_factory=dict)
    poster_mappings: dict[str, str] = field(default_factory=dict)
    validation_rules: list[ValidationRule] = field(default_factory=list)
    date_rules: dict[str, str] = field(default_factory=dict)
    naming_rule: NamingRule | None = None
    output_folders: dict[str, str] = field(default_factory=dict)
