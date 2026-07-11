# Office Automation Platform - API server image.
#
# This image runs the FastAPI backend only (app.api.main) - the PySide6
# desktop GUI is installed per-workstation (see docs/INSTALLATION.md) and
# is intentionally never built into this image; requirements-server.txt
# excludes it and every other desktop-only dependency.
#
# Multi-stage build: the `builder` stage compiles/installs Python
# dependencies into an isolated virtualenv; the final stage copies only
# that venv plus the application source, so no build tooling or pip cache
# ends up in the shipped image.

FROM python:3.12-slim AS builder

WORKDIR /build

# Wheels exist for every pin in requirements-server.txt on this base image
# (slim already ships the shared libs pypdf/pikepdf/Pillow/psycopg2-binary
# need at runtime) - no extra system -dev packages are required to build.
RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

COPY requirements-server.txt ./
RUN pip install --no-cache-dir --upgrade pip \
    && pip install --no-cache-dir -r requirements-server.txt


FROM python:3.12-slim AS runtime

LABEL org.opencontainers.image.title="Office Automation Platform API" \
      org.opencontainers.image.description="FastAPI backend for the Office Automation Platform" \
      org.opencontainers.image.licenses="Proprietary"

# Run as a dedicated, unprivileged user - never as root. UID/GID are
# pinned (rather than left to a dynamically-assigned system UID) because
# docker-compose.yml bind-mounts a host directory over /app/data: bind
# mounts keep the *host's* ownership, so the container's process can only
# write to it if that host directory is chowned to a UID/GID it knows in
# advance. See docs/DEPLOYMENT.md's installation steps, which chown the
# host's ./data to this exact UID/GID before first start.
RUN groupadd --gid 1000 oap && useradd --uid 1000 --gid oap --home-dir /app --create-home oap

COPY --from=builder /opt/venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH" \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

WORKDIR /app

# Application code, migrations, and default rule/workflow configuration.
# .env is deliberately NOT copied in (see .dockerignore) - it is supplied
# at container-run time via `env_file:` / `--env-file`, never baked into
# the image.
COPY app/ ./app/
COPY alembic/ ./alembic/
COPY alembic.ini ./
COPY config/ ./config/
COPY docker/entrypoint.sh ./docker/entrypoint.sh
RUN chmod +x ./docker/entrypoint.sh

# Directories the app writes to at runtime (documents, logs, backups) -
# created here so they exist with correct ownership even before a volume
# is mounted over them.
RUN mkdir -p /app/data/import /app/data/archive /app/data/export /app/data/backups /app/data/logs \
    && chown -R oap:oap /app

USER oap

EXPOSE 8000

# start-period is generous (60s) because the entrypoint (docker/entrypoint.sh)
# waits for PostgreSQL and runs `alembic upgrade head` before the process
# even starts listening - a slow first boot (cold DB, larger migration)
# must not be misreported as "unhealthy" while it's still legitimately starting.
HEALTHCHECK --interval=30s --timeout=5s --start-period=60s --retries=3 \
    CMD python -c "import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:8000/health', timeout=3).status == 200 else 1)"

# Runs via app.api.main:run(), which reads host/port/reload from Settings
# (OAP_API_HOST/OAP_API_PORT/OAP_API_RELOAD) - set OAP_API_HOST=0.0.0.0 in
# the container's environment (docker-compose.yml already does this) so it
# actually listens on the container's external interface, not just
# loopback. Using the app's own entrypoint here (rather than invoking
# uvicorn directly with hardcoded flags) keeps one source of truth for
# host/port instead of two places that could silently drift apart.
ENTRYPOINT ["./docker/entrypoint.sh"]
CMD ["python", "-m", "app.api.main"]
