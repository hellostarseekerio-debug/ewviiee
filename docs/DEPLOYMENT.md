# Production Deployment Guide

This guide covers deploying the API backend for real office use behind a
reverse proxy, with TLS, process supervision, and the configuration
changes that differ from local development. For the desktop GUI, see
`docs/INSTALLATION.md` and `docs/TROUBLESHOOTING.md` (the GUI is installed
per-workstation, not deployed as a service).

## 1. Topology

```
                      ┌─────────────────────────┐
 Office workstations  │  Reverse proxy (TLS)     │
 (desktop GUI, or     │  nginx / Caddy / IIS ARR │
 browser via Swagger) │  :443                    │
        │             └───────────┬─────────────┘
        │                         │ HTTP, 127.0.0.1 only
        ▼                         ▼
                      ┌─────────────────────────┐
                      │  uvicorn (app.api.main)  │
                      │  :8000, bound to         │
                      │  127.0.0.1 only          │
                      └───────────┬─────────────┘
                                  │
                      ┌───────────┴─────────────┐
                      │ SQLite file / PostgreSQL │
                      │ data/archive, data/export│
                      └─────────────────────────┘
```

The API is designed to sit behind a reverse proxy that terminates TLS - it
does not serve HTTPS itself. `OAP_API_HOST` defaults to `127.0.0.1`
specifically so an operator has to make a deliberate choice to expose it
more broadly, rather than accidentally binding to `0.0.0.0` on a machine
with a public interface.

## 2. Environment configuration checklist

Before starting the service for real use, confirm every item below.
`Settings.assert_secure_for_production()` enforces the first three
automatically when `OAP_ENVIRONMENT=production` and will refuse to start
otherwise - the rest are not automatically enforced and must be checked by
whoever deploys the system.

- [ ] `OAP_ENVIRONMENT=production`
- [ ] `OAP_SECRET_KEY` - unique, random (`python -c "import secrets; print(secrets.token_urlsafe(48))"`)
- [ ] `OAP_ENCRYPTION_KEY` - unique, random (`python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"`), backed up somewhere safe (losing it makes encrypted data, including MFA secrets, unrecoverable)
- [ ] `OAP_CORS_ALLOWED_ORIGINS` - the exact origin(s) of any browser client, never `*`
- [ ] `OAP_API_HOST=127.0.0.1` (default) with the reverse proxy handling external traffic, unless you have a specific, reviewed reason to bind wider
- [ ] `OAP_API_RELOAD` left unset/false (auto-reload is a development convenience and must never run in production)
- [ ] `OAP_DATABASE_BACKEND` - `sqlite` is fine for a single office; use `postgresql` if you expect concurrent write load beyond what SQLite handles well (see "Choosing SQLite vs PostgreSQL" below)
- [ ] `OAP_AI_PROVIDER=local` unless the office has made a deliberate, documented decision to use a cloud provider (see `docs/PRIVACY.md`) - and even then, `allow_cloud_ai` still defaults off until an admin flips it
- [ ] Backups scheduled (`scripts/backup_db.py`) - see `docs/admin_guide.md` and the recovery test below
- [ ] First administrator account created via `scripts/create_admin.py`, **not** left as an open bootstrap endpoint reachable from the network
- [ ] MFA enabled for all admin accounts at minimum (`docs/SECURITY.md`)

## 3. Choosing SQLite vs PostgreSQL

SQLite (the default) is appropriate for a single Legislative Council
office: one write path, moderate concurrency, zero operational overhead,
and it has been load-tested up to several thousand document rows in this
repository's test suite (see `docs/PRIVACY.md`'s sibling,
`tests/performance/test_scale.py`) with sub-second search performance.

Move to PostgreSQL (`OAP_DATABASE_BACKEND=postgresql`,
`OAP_POSTGRES_DSN=...`, `pip install -e ".[postgres]"`) if:
- multiple API worker processes will write concurrently under sustained
  load (SQLite serializes writers), or
- your IT policy requires a managed database server with its own
  backup/HA tooling.

Either way, run `alembic upgrade head` after switching backends.

## 4. Running as a supervised service

### systemd (Linux)

```ini
# /etc/systemd/system/office-automation-api.service
[Unit]
Description=Office Automation Platform API
After=network.target

[Service]
Type=simple
User=oap
WorkingDirectory=/opt/office-automation
EnvironmentFile=/opt/office-automation/.env
ExecStart=/opt/office-automation/.venv/bin/python -m app.api.main
Restart=on-failure
RestartSec=5
# Hardening
NoNewPrivileges=true
PrivateTmp=true
ProtectSystem=strict
ReadWritePaths=/opt/office-automation/data

[Install]
WantedBy=multi-user.target
```

```bash
sudo systemctl daemon-reload
sudo systemctl enable --now office-automation-api
sudo systemctl status office-automation-api
```

### Multiple workers

`python -m app.api.main` runs a single uvicorn worker, which is sufficient
for a typical office's concurrent load and keeps the in-memory rate
limiter and cached plugin manager consistent. If you need multiple worker
processes (e.g. `uvicorn app.api.main:app --workers 4`), be aware:

- The `slowapi` rate limiter's default in-memory storage does **not**
  share state across worker processes - each worker enforces its own
  counter, effectively multiplying the configured limit by the worker
  count. For multi-worker deployments, configure a shared backend (Redis)
  via `slowapi`'s `storage_uri` option in `app/api/rate_limit.py`.
- This does not affect account lockout (stored in the database, shared
  correctly across workers) - only the IP-based rate limiter.

## 5. Reverse proxy example (nginx)

```nginx
server {
    listen 443 ssl http2;
    server_name office-automation.example.gov.hk;

    ssl_certificate     /etc/ssl/certs/office-automation.pem;
    ssl_certificate_key /etc/ssl/private/office-automation.key;

    client_max_body_size 30m;  # slightly above OAP_MAX_UPLOAD_SIZE_BYTES

    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}

server {
    listen 80;
    server_name office-automation.example.gov.hk;
    return 301 https://$host$request_uri;
}
```

The application's own security headers (`app.api.main.SecurityHeadersMiddleware`)
still apply behind the proxy; nginx does not need to duplicate them.

## 6. Health checks and monitoring

- `GET /health` returns `{"status": "ok", "app": "..."}` - use this for the
  reverse proxy's / load balancer's health check and for an uptime monitor.
- Application logs: `data/logs/application.log` (structured JSON lines).
  Ship these to your log aggregator of choice by tailing the file, or
  redirect the process's stdout (structlog is configured to also print to
  stdout) into your platform's log collector.
- The `audit_logs` table is the authoritative record of security-relevant
  events (logins, permission denials, uploads, workflow runs, approvals,
  settings changes) - consider a periodic export (`app.core.logging_config.export_logs`)
  to your office's log retention system if one exists.

## 7. Upgrading

```bash
git pull
source .venv/bin/activate
pip install -r requirements.txt
alembic upgrade head
sudo systemctl restart office-automation-api   # or your process manager
```

Always take a backup (`python scripts/backup_db.py`) before running a new
migration.

## 8. What this deployment model deliberately does not include

- Built-in TLS termination - use a reverse proxy.
- Built-in horizontal scaling / load balancing across machines - this is
  sized for a single office's document volume, not a multi-tenant SaaS.
- Automatic failover / high availability - if that's required, it belongs
  at the PostgreSQL and reverse-proxy layers, which are standard,
  well-documented problems independent of this application.
