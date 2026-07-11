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
    monkeypatch.setenv("OAP_LOCAL_IMPORT_ROOT", str(tmp_path / "data" / "import"))
    monkeypatch.setenv("OAP_AI_PROVIDER", "local")
    # Rate limits are exercised by a dedicated test with its own low limit;
    # keep the default high here so unrelated tests hitting the same
    # in-process endpoint repeatedly don't trip each other's counters.
    monkeypatch.setenv("OAP_RATE_LIMIT_LOGIN", "1000/minute")
    monkeypatch.setenv("OAP_RATE_LIMIT_DEFAULT", "1000/minute")

    from app.api.deps import get_plugin_manager
    from app.core.config import get_settings
    from app.core.database import reset_engine

    get_settings.cache_clear()
    reset_engine()
    get_plugin_manager.cache_clear()
    yield
    get_settings.cache_clear()
    reset_engine()
    get_plugin_manager.cache_clear()


@pytest.fixture
def api_client(tmp_path):
    """A TestClient with the FastAPI lifespan (startup/shutdown) triggered,
    so `init_db()` actually runs before requests hit the app."""
    from fastapi.testclient import TestClient

    from app.api.main import app

    with TestClient(app) as client:
        yield client


@pytest.fixture
def bootstrap_admin(api_client):
    """Creates the first (bootstrap) admin account and returns
    (client, headers) ready to call admin-only endpoints."""
    api_client.post(
        "/api/auth/users",
        json={"username": "admin", "password": "SuperSecret123!", "role": "admin"},
    )
    response = api_client.post(
        "/api/auth/token", data={"username": "admin", "password": "SuperSecret123!"}
    )
    token = response.json()["access_token"]
    return api_client, {"Authorization": f"Bearer {token}"}
