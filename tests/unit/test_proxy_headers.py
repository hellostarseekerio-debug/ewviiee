"""Verifies the reverse-proxy client-IP fix: without it, every request
behind a reverse proxy appears to come from the proxy's own address,
turning slowapi's per-client rate limiting into one shared bucket for
every user. `OAP_TRUST_PROXY_HEADERS` opts into trusting X-Forwarded-For
from a configured set of directly-connecting peers."""
from __future__ import annotations

from fastapi import Request

from app.api.main import _wrap_for_proxy, create_app
from app.core.config import Settings


def _build_client_probe_app(settings: Settings):
    app = create_app()

    @app.get("/whoami")
    def whoami(request: Request):
        return {"client": request.client.host if request.client else None}

    return _wrap_for_proxy(app, settings)


def test_client_ip_unaffected_by_forwarded_header_when_disabled():
    from starlette.testclient import TestClient

    settings = Settings(trust_proxy_headers=False)
    wrapped = _build_client_probe_app(settings)

    with TestClient(wrapped) as client:
        response = client.get("/whoami", headers={"X-Forwarded-For": "203.0.113.42"})
    assert response.json()["client"] != "203.0.113.42"


def test_client_ip_taken_from_forwarded_header_when_enabled_and_trusted():
    from starlette.testclient import TestClient

    settings = Settings(trust_proxy_headers=True, trusted_proxy_hosts="*")
    wrapped = _build_client_probe_app(settings)

    with TestClient(wrapped) as client:
        response = client.get("/whoami", headers={"X-Forwarded-For": "203.0.113.42"})
    assert response.json()["client"] == "203.0.113.42"


def test_untrusted_peer_forwarded_header_is_ignored():
    from starlette.testclient import TestClient

    # Only 198.51.100.1 is trusted to set X-Forwarded-For - the test
    # client's actual connecting address ("testclient") is not in that
    # set, so the header must be ignored.
    settings = Settings(trust_proxy_headers=True, trusted_proxy_hosts="198.51.100.1")
    wrapped = _build_client_probe_app(settings)

    with TestClient(wrapped) as client:
        response = client.get("/whoami", headers={"X-Forwarded-For": "203.0.113.42"})
    assert response.json()["client"] != "203.0.113.42"
