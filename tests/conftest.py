from __future__ import annotations

from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent


@pytest.fixture(autouse=True)
def _isolated_settings(tmp_path, monkeypatch):
    """Point the app at a scratch data dir per test and the real config dir,
    then clear the settings cache so each test gets a fresh Settings object."""
    monkeypatch.setenv("OAP_DATA_DIR", str(tmp_path / "data"))
    monkeypatch.setenv("OAP_SQLITE_PATH", str(tmp_path / "data" / "test.db"))
    monkeypatch.setenv("OAP_CONFIG_DIR", str(REPO_ROOT / "config"))
    monkeypatch.setenv("OAP_ARCHIVE_ROOT", str(tmp_path / "data" / "archive"))
    monkeypatch.setenv("OAP_EXPORT_ROOT", str(tmp_path / "data" / "export"))
    monkeypatch.setenv("OAP_AI_PROVIDER", "local")

    from app.core.config import get_settings

    get_settings.cache_clear()
    yield
    get_settings.cache_clear()
