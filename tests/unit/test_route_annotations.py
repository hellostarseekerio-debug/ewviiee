"""Regression test for a Render deploy crash: FastAPI==0.111.0 (the version
actually pinned in requirements.txt/requirements-server.txt) raised
`TypeError: ForwardRef('OAuth2PasswordRequestForm') is not a callable
object` while registering POST /api/auth/token at startup.

Root cause: every route in auth.py/documents.py/workflows.py decorated
with `@limiter.limit(...)` (slowapi) is wrapped before FastAPI ever sees
it. FastAPI resolves PEP 563 deferred string annotations (from
`from __future__ import annotations`) using the *decorated* function's
`__globals__` - which is slowapi's own module, not the route module - so
any annotation naming something slowapi doesn't itself import
(OAuth2PasswordRequestForm, UploadFile, WorkflowRunRequest, etc.) stayed
an unresolved ForwardRef and broke route registration. Newer FastAPI
versions happen to tolerate this, which is why it wasn't caught against
this project's ad hoc local dev environment (which had drifted to a
newer FastAPI than the pin) - only a real pinned-version deploy surfaced
it. Fixed by removing `from __future__ import annotations` from the three
affected route modules, so annotations are live objects at decoration
time regardless of decorator wrapping.

This test doesn't reproduce the FastAPI-version-specific symptom directly
(that requires the exact pinned versions - see requirements-server.txt),
but constructing the app and exercising /api/auth/token end-to-end here
covers the same code path CI's `pip install -r requirements.txt` (which
does install the exact pinned versions) will exercise on every run.
"""
from __future__ import annotations


def test_create_app_registers_every_route_without_error():
    """The bug crashed while *registering* routes (module import time), so
    just reaching this line without an exception is most of the
    regression coverage - `app.routes` introspection is intentionally
    avoided since FastAPI's internal route representation isn't stable
    across versions."""
    from app.api.main import create_app

    create_app()


def test_previously_broken_routes_are_reachable(api_client):
    """Each of these lives in a module that was affected
    (auth.py/documents.py/workflows.py) - a 404 here would mean route
    registration silently dropped the route instead of raising, which the
    exception-based test above wouldn't catch."""
    assert api_client.post("/api/auth/token", data={}).status_code != 404
    assert api_client.post("/api/documents/upload").status_code != 404
    assert api_client.post("/api/workflows/run", json={}).status_code != 404


def test_login_route_end_to_end(api_client):
    """Exercises the exact endpoint that crashed at startup - if route
    registration silently produced a broken dependant for `form_data`,
    this request would fail well before reaching password verification."""
    api_client.post(
        "/api/auth/users",
        json={"username": "regression_admin", "password": "SuperSecret123!", "role": "admin"},
    )
    response = api_client.post(
        "/api/auth/token",
        data={"username": "regression_admin", "password": "SuperSecret123!"},
    )
    assert response.status_code == 200
    assert "access_token" in response.json()
