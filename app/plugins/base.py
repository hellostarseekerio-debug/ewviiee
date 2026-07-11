"""Plugin interface.

Every office workflow (Housing Estate Posters, Banner Applications,
Government Forms, ...) is a Plugin. The core application never imports a
specific plugin module directly - the PluginManager discovers and loads
plugins by name from `app/plugins/<plugin_name>/` (or an external directory),
so new workflows can be added by dropping in a plugin package plus a
workflow YAML file, without touching core code.
"""
from __future__ import annotations

from typing import Protocol

from app.core.config import Settings
from app.rules.engine import RuleEngine
from app.workflow.stages import StageHandler


class Plugin(Protocol):
    """A workflow plugin. `plugin_id` must match the `plugin:` field used in
    the corresponding config/workflows/*.yaml file."""

    plugin_id: str
    display_name: str
    version: str

    def initialize(self, settings: Settings, rule_engine: RuleEngine) -> None:
        ...

    def get_stage_handlers(self) -> dict[str, StageHandler]:
        ...


class BasePlugin:
    """Convenience base class plugins may inherit from."""

    plugin_id: str = "base"
    display_name: str = "Base Plugin"
    version: str = "0.1.0"

    def __init__(self) -> None:
        self.settings: Settings | None = None
        self.rule_engine: RuleEngine | None = None

    def initialize(self, settings: Settings, rule_engine: RuleEngine) -> None:
        self.settings = settings
        self.rule_engine = rule_engine

    def get_stage_handlers(self) -> dict[str, StageHandler]:
        raise NotImplementedError
