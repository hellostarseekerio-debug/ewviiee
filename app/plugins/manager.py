"""Discovers, loads and manages the lifecycle of workflow plugins.

Plugins live as Python packages under `app/plugins/<plugin_id>/` and must
expose a module-level `PLUGIN_CLASS` in their `plugin.py`. Only plugins
listed in `Settings.enabled_plugins` are instantiated, so an admin can
disable a workflow without deleting its code.
"""
from __future__ import annotations

import importlib

from app.ai.factory import get_guarded_ai_provider
from app.core.config import Settings, get_settings
from app.core.logging_config import get_logger
from app.plugins.base import Plugin
from app.rules.engine import RuleEngine, load_ruleset

logger = get_logger("plugins.manager")


class PluginManager:
    def __init__(self, settings: Settings | None = None) -> None:
        self._settings = settings or get_settings()
        self._plugins: dict[str, Plugin] = {}

    def discover_and_load(self) -> dict[str, Plugin]:
        ruleset = load_ruleset(self._settings.config_dir)
        rule_engine = RuleEngine(ruleset, ai_provider=self._safe_ai_provider())

        for plugin_id in self._settings.enabled_plugins:
            try:
                module = importlib.import_module(f"app.plugins.{plugin_id}.plugin")
                plugin_class = getattr(module, "PLUGIN_CLASS")
                plugin_instance: Plugin = plugin_class()
                plugin_instance.initialize(self._settings, rule_engine)
                self._plugins[plugin_instance.plugin_id] = plugin_instance
                logger.info("plugin_loaded", plugin_id=plugin_instance.plugin_id)
            except Exception as exc:
                logger.error("plugin_load_failed", plugin_id=plugin_id, error=str(exc))

        return self._plugins

    def _safe_ai_provider(self):
        try:
            return get_guarded_ai_provider(self._settings)
        except Exception as exc:
            logger.warning("ai_provider_unavailable", error=str(exc))
            return None

    def get_plugin(self, plugin_id: str) -> Plugin | None:
        return self._plugins.get(plugin_id)

    def list_plugins(self) -> list[Plugin]:
        return list(self._plugins.values())
