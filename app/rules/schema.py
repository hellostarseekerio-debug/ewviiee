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


@dataclass
class Estate:
    id: str
    name: str
    district_id: str
    aliases: list[str] = field(default_factory=list)


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
