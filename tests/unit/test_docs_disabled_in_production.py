"""Verifies /docs, /redoc, and /openapi.json are only reachable outside
production. Publicly exposing the interactive API docs and raw schema
hands anyone who finds the URL a map of every endpoint and request/
response field, with no authentication required to view it - acceptable
while developing, unnecessary reconnaissance surface on a real
internet-facing deployment."""
from __future__ import annotations

from starlette.testclient import TestClient

from app.api.main import create_app
from app.core.config import get_settings


def test_docs_available_outside_production():
    with TestClient(create_app()) as client:
        assert client.get("/docs").status_code == 200
        assert client.get("/redoc").status_code == 200
        assert client.get("/openapi.json").status_code == 200


def test_docs_disabled_in_production(monkeypatch):
    monkeypatch.setenv("OAP_ENVIRONMENT", "production")
    monkeypatch.setenv("OAP_SECRET_KEY", "test-secret-key-for-docs-check-32-chars-long")
    monkeypatch.setenv("OAP_ENCRYPTION_KEY", "dGVzdC1lbmNyeXB0aW9uLWtleS0zMi1ieXRlcy1sb25nISE=")
    monkeypatch.setenv("OAP_CORS_ALLOWED_ORIGINS", '["https://example.onrender.com"]')
    get_settings.cache_clear()

    try:
        with TestClient(create_app()) as client:
            assert client.get("/docs").status_code == 404
            assert client.get("/redoc").status_code == 404
            assert client.get("/openapi.json").status_code == 404
            assert client.get("/health").status_code == 200
    finally:
        get_settings.cache_clear()
