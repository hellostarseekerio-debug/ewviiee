"""Verifies SecurityHeadersMiddleware's Content-Security-Policy: the
default strict policy (`default-src 'self'`) blocks FastAPI's built-in
/docs and /redoc pages entirely, since those load their JS/CSS from a CDN
and run a small inline init script - the page loads but renders blank,
with no visible error other than CSP violations in the browser console.
Only /docs, /redoc, and /docs/oauth2-redirect get a named CDN exception;
every other route (the actual JSON API) must keep the original strict
policy unchanged."""
from __future__ import annotations

from app.api.main import create_app


def test_docs_page_gets_relaxed_csp_and_renders():
    from starlette.testclient import TestClient

    with TestClient(create_app()) as client:
        response = client.get("/docs")

    assert response.status_code == 200
    csp = response.headers["content-security-policy"]
    assert "cdn.jsdelivr.net" in csp
    assert "swagger-ui-bundle.js" in response.text


def test_redoc_page_gets_relaxed_csp():
    from starlette.testclient import TestClient

    with TestClient(create_app()) as client:
        response = client.get("/redoc")

    assert response.status_code == 200
    assert "cdn.jsdelivr.net" in response.headers["content-security-policy"]


def test_api_routes_keep_the_strict_default_csp():
    from starlette.testclient import TestClient

    with TestClient(create_app()) as client:
        response = client.get("/api/documents")

    assert response.headers["content-security-policy"] == "default-src 'self'; frame-ancestors 'none'"


def test_health_route_keeps_the_strict_default_csp():
    from starlette.testclient import TestClient

    with TestClient(create_app()) as client:
        response = client.get("/health")

    assert response.headers["content-security-policy"] == "default-src 'self'; frame-ancestors 'none'"
