"""FastAPI application entrypoint."""
from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from starlette.middleware.base import BaseHTTPMiddleware

from app.api.rate_limit import limiter
from app.api.routes import auth, documents, plugins, search, settings as settings_routes, workflows
from app.core.config import get_settings
from app.core.database import init_db
from app.core.logging_config import configure_logging, get_logger

logger = get_logger("api.main")


@asynccontextmanager
async def _lifespan(app: FastAPI):
    init_db()
    yield



# FastAPI's built-in /docs (Swagger UI) and /redoc pages load their JS/CSS
# from this CDN and run a small inline init script - the default strict
# CSP below blocks all of that with no error dialog, just a blank page.
# Only these dev-tooling routes (never the JSON API itself, which doesn't
# execute any script regardless of CSP) get the relaxed policy below.
_DOCS_PATHS = frozenset({"/docs", "/redoc", "/docs/oauth2-redirect"})
_DOCS_CSP = (
    "default-src 'self'; "
    "script-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net; "
    "style-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net; "
    "img-src 'self' data: https://fastapi.tiangolo.com https://cdn.jsdelivr.net; "
    "font-src 'self' https://cdn.jsdelivr.net; "
    "connect-src 'self'; "
    "frame-ancestors 'none'"
)
_DEFAULT_CSP = "default-src 'self'; frame-ancestors 'none'"


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """Adds standard defensive HTTP headers to every response. This is a
    local-first, internal-office application, so the CSP is deliberately
    strict (no external script/style/font sources) everywhere except the
    interactive API docs pages, which need a named CDN exception to
    render at all - see _DOCS_PATHS above."""

    async def dispatch(self, request: Request, call_next):
        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Referrer-Policy"] = "no-referrer"
        response.headers["Permissions-Policy"] = "camera=(), microphone=(), geolocation=()"
        response.headers["Content-Security-Policy"] = (
            _DOCS_CSP if request.url.path in _DOCS_PATHS else _DEFAULT_CSP
        )
        response.headers["Strict-Transport-Security"] = "max-age=63072000; includeSubDomains"
        return response


def create_app() -> FastAPI:
    configure_logging()
    settings = get_settings()
    settings.assert_secure_for_production()

    app = FastAPI(
        title=settings.app_name,
        version="0.1.0",
        description="Enterprise AI Office Automation Platform API",
        lifespan=_lifespan,
    )

    app.state.limiter = limiter
    app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
    app.add_middleware(SecurityHeadersMiddleware)

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_allowed_origins,
        allow_credentials=True,
        allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE"],
        allow_headers=["Authorization", "Content-Type"],
    )

    app.include_router(auth.router)
    app.include_router(documents.router)
    app.include_router(search.router)
    app.include_router(workflows.router)
    app.include_router(plugins.router)
    app.include_router(settings_routes.router)

    @app.exception_handler(Exception)
    async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
        """Never leak internals (stack traces, file paths, query text) to the
        client - log the full detail server-side and return a generic message."""
        logger.error("unhandled_exception", path=str(request.url), error=str(exc))
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={"detail": "An internal error occurred. It has been logged for review."},
        )

    @app.get("/health")
    def health() -> dict:
        return {"status": "ok", "app": settings.app_name}

    return app


def _wrap_for_proxy(asgi_app: FastAPI, settings) -> FastAPI:
    """When behind a reverse proxy, every request otherwise appears to
    slowapi's `get_remote_address` (and to anything else that reads
    `request.client.host`) to come from the proxy's own address - turning
    per-IP rate limiting into one shared bucket for every user, since they
    would all appear to share a single "IP". `ProxyHeadersMiddleware`
    rewrites the ASGI scope's client address from X-Forwarded-For before
    Starlette/FastAPI ever see the request, so this must wrap the
    outermost app, not be added via `app.add_middleware`."""
    if not settings.trust_proxy_headers:
        return asgi_app
    from uvicorn.middleware.proxy_headers import ProxyHeadersMiddleware

    return ProxyHeadersMiddleware(asgi_app, trusted_hosts=settings.trusted_proxy_hosts)


app = _wrap_for_proxy(create_app(), get_settings())


def run() -> None:
    import uvicorn

    settings = get_settings()
    uvicorn.run(
        "app.api.main:app",
        host=settings.api_host,
        port=settings.api_port,
        reload=settings.api_reload,
    )


if __name__ == "__main__":
    run()
