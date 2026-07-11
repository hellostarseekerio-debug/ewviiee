# Production Deployment Guide

This guide covers deploying the API backend for real office use: as a
Docker Compose stack (recommended for a cloud server) or directly on
bare metal with systemd - behind a reverse proxy, with TLS, process
supervision, and the configuration changes that differ from local
development. For the desktop GUI, see `docs/INSTALLATION.md` and
`docs/TROUBLESHOOTING.md` (the GUI is installed per-workstation, not
deployed as a service).

## 1. Server requirements

| Resource | Minimum | Notes |
|---|---|---|
| CPU | 2 vCPU | OCR/PDF generation is CPU-bound but runs per-document, not continuously |
| RAM | 2 GB (4 GB with Docker + PostgreSQL) | PaddleOCR, if enabled, benefits from more |
| Disk | 20 GB, SSD preferred | Grows with archived documents + backups; size for your office's expected volume and retention period |
| OS | Any Linux with Docker support (Ubuntu 22.04/24.04 LTS recommended), or Windows Server for a bare-metal Python deployment | Docker Compose deployment is OS-agnostic beyond needing Docker itself |
| Software (Docker route) | Docker Engine 24+, Docker Compose v2 (`docker compose`, not the standalone `docker-compose`) | `docker compose version` to check |
| Software (bare-metal route) | Python 3.12+, optionally Tesseract OCR binary, optionally PostgreSQL 14+ | See `docs/INSTALLATION.md` |
| Network | Outbound HTTPS only if using a cloud AI provider (off by default) or cloud import sources; otherwise no internet access required at all | Local-first by design - see `docs/PRIVACY.md` |

A single small cloud VM (e.g. 2 vCPU / 4 GB RAM) comfortably serves one
Legislative Council office's document volume; this is not sized for a
multi-office SaaS deployment.

## 2. Environment configuration checklist

Before starting the service for real use, confirm every item below.
`Settings.assert_secure_for_production()` enforces the first four
automatically when `OAP_ENVIRONMENT=production` and will refuse to start
otherwise - the rest are not automatically enforced and must be checked by
whoever deploys the system.

- [ ] `OAP_ENVIRONMENT=production`
- [ ] `OAP_SECRET_KEY` - unique, random, 32+ characters (`python -c "import secrets; print(secrets.token_urlsafe(48))"`)
- [ ] `OAP_ENCRYPTION_KEY` - unique, random (`python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"`), backed up somewhere safe (losing it makes encrypted data, including MFA secrets, unrecoverable)
- [ ] `OAP_CORS_ALLOWED_ORIGINS` - the exact origin(s) of any browser client, never `*`
- [ ] `OAP_API_HOST=127.0.0.1` (default) with the reverse proxy handling external traffic, unless you have a specific, reviewed reason to bind wider (the Docker Compose stack overrides this to `0.0.0.0` internally - see §4 - while still only publishing to the host's loopback interface)
- [ ] `OAP_API_RELOAD` left unset/false (auto-reload is a development convenience and must never run in production)
- [ ] `OAP_DATABASE_BACKEND` - `sqlite` is fine for a single office; use `postgresql` if you expect concurrent write load beyond what SQLite handles well (see §3) - the Docker Compose stack always uses PostgreSQL
- [ ] `OAP_AI_PROVIDER=local` unless the office has made a deliberate, documented decision to use a cloud provider (see `docs/PRIVACY.md`) - and even then, `allow_cloud_ai` still defaults off until an admin flips it
- [ ] Backups scheduled (`scripts/backup_db.py` or `scripts/docker_backup_postgres.sh`) - see §6 and the recovery test in `tests/integration/test_backup_restore.py`
- [ ] First administrator account created via `scripts/create_admin.py`, **not** left as an open bootstrap endpoint reachable from the network
- [ ] MFA enabled for all admin accounts at minimum (`docs/SECURITY.md`)

## 3. Choosing SQLite vs PostgreSQL

SQLite is appropriate for a single Legislative Council office running the
bare-metal deployment: one write path, moderate concurrency, zero
operational overhead, and it has been load-tested up to several thousand
document rows in this repository's test suite (`tests/performance/test_scale.py`)
with sub-second search performance.

The **Docker Compose deployment always uses PostgreSQL** (§4) - it is
better suited to a containerized, cloud-server deployment (a managed
volume/service you can back up, monitor, and eventually migrate to a
managed database independent of the app container), and removes SQLite's
single-writer limitation if your office's volume grows.

Either way, `alembic upgrade head` runs automatically on every container
start (see the entrypoint in §4); for bare metal, run it manually after
switching backends or upgrading.

## 4. Docker deployment (recommended for a cloud server)

### 4.1 Installation steps

```bash
# On the server:
git clone <this repository> /opt/office-automation
cd /opt/office-automation

cp .env.docker.example .env
# Edit .env: set POSTGRES_PASSWORD, OAP_SECRET_KEY, OAP_ENCRYPTION_KEY,
# OAP_CORS_ALLOWED_ORIGINS at minimum - see the checklist in §2 and the
# comments in .env.docker.example.
nano .env

# The container runs as a fixed non-root uid:gid (1000:1000) and
# ./data is bind-mounted into it - pre-create it with matching ownership
# so the app can actually write documents/logs/backups there.
mkdir -p data
sudo chown -R 1000:1000 data

docker compose build
docker compose up -d
docker compose logs -f api   # watch startup; Ctrl-C to stop watching (the stack keeps running)
```

On first start, the `api` container's entrypoint (`docker/entrypoint.sh`)
waits for PostgreSQL to become reachable and then runs
`alembic upgrade head` automatically before starting the server - there is
no separate manual migration step for a fresh install.

### 4.2 Database setup

The `db` service (`postgres:16-alpine`) is created automatically by
`docker compose up`, using `POSTGRES_USER` / `POSTGRES_PASSWORD` /
`POSTGRES_DB` from `.env`. Its data lives in the named Docker volume
`postgres_data`, which persists across `docker compose down` /
`docker compose up` cycles (only `docker compose down -v` would remove
it - avoid that in production). The database is **not** published to the
host or the internet; only the `api` service can reach it, over the
internal `oap_internal` Docker network.

### 4.3 Migration process

Migrations run automatically on every `api` container start/restart
(`docker/entrypoint.sh` → `alembic upgrade head`), so upgrading the
application (§4.5) always includes migrating the schema. To run a
migration manually without restarting the whole stack (e.g. to check
pending migrations):

```bash
docker compose exec api alembic current      # shows the currently applied revision
docker compose exec api alembic upgrade head # safe to re-run - no-op if already current
```

### 4.4 Creating the first administrator account

Do this directly against the database container - never expose the
bootstrap network endpoint on a real deployment:

```bash
docker compose exec api python scripts/create_admin.py --username admin --full-name "Jane Doe"
```

### 4.5 Backup setup

```bash
# Run manually, or add to root's crontab for a nightly schedule, e.g.:
#   0 2 * * * cd /opt/office-automation && bash scripts/docker_backup_postgres.sh >> data/logs/backup.log 2>&1
bash scripts/docker_backup_postgres.sh
```

This produces two files under `data/backups/`: a PostgreSQL custom-format
dump (`postgres_<timestamp>.dump`) and a tarball of
`data/archive`+`data/export`+`data/import` (`files_<timestamp>.tar.gz`),
and prunes backups older than `OAP_BACKUP_RETENTION_DAYS`. Copy
`data/backups/` off the server on the same schedule (a compromised server
should not also compromise its own backups).

**Restoring:**

```bash
bash scripts/docker_restore_postgres.sh data/backups/postgres_<timestamp>.dump data/backups/files_<timestamp>.tar.gz
```

This always takes a fresh safety backup of the current state before
overwriting anything, and prompts for confirmation unless `--yes` is
passed. See `tests/integration/test_backup_restore.py` for the equivalent
tested procedure on the SQLite/bare-metal path - the Postgres path here
follows the same principle (safety backup first, explicit confirmation)
but is a shell script wrapping `pg_dump`/`pg_restore` rather than Python,
since it orchestrates `docker compose exec` rather than the app itself.

### 4.6 Upgrading

```bash
cd /opt/office-automation
git pull
bash scripts/docker_backup_postgres.sh   # always back up before upgrading
docker compose build
docker compose up -d
docker compose logs -f api                # migrations run automatically on start
```

### 4.7 Useful commands

```bash
docker compose ps                 # service status
docker compose logs -f api        # follow API logs
docker compose exec api bash      # shell inside the API container
docker compose restart api        # restart just the API (e.g. after an env change)
docker compose down               # stop everything (keeps volumes/data)
```

## 5. HTTPS setup

The API container/process never terminates TLS itself - `OAP_API_HOST`
and the Compose `ports:` mapping both keep it reachable only from
`127.0.0.1` on the host. Put a reverse proxy in front for real traffic.

**Whenever a reverse proxy is in front, also set `OAP_TRUST_PROXY_HEADERS=true`**
(already the default in `.env.docker.example`). Without it, every request
appears to the app to come from the proxy's own address - turning per-IP
rate limiting (login attempts, uploads) into one shared bucket for every
user in the office, since they'd all appear to share a single "IP".
`OAP_TRUSTED_PROXY_HOSTS` controls which directly-connecting peers are
allowed to set `X-Forwarded-For` (default `127.0.0.1`; the Docker Compose
template uses `*`, safe there specifically because the published port
isn't reachable except from the same host - see the comment in
`.env.docker.example`). Both nginx configs below already send the
required `X-Forwarded-For`/`X-Real-IP` headers.

### Option A: nginx + Let's Encrypt (Certbot), on the host

```bash
sudo apt install nginx certbot python3-certbot-nginx
```

```nginx
# /etc/nginx/sites-available/office-automation
server {
    listen 80;
    server_name office-automation.example.gov.hk;
    return 301 https://$host$request_uri;
}

server {
    listen 443 ssl http2;
    server_name office-automation.example.gov.hk;

    # Certbot fills these in and manages renewal after the next command.
    ssl_certificate     /etc/letsencrypt/live/office-automation.example.gov.hk/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/office-automation.example.gov.hk/privkey.pem;

    client_max_body_size 30m;  # slightly above OAP_MAX_UPLOAD_SIZE_BYTES

    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```

```bash
sudo ln -s /etc/nginx/sites-available/office-automation /etc/nginx/sites-enabled/
sudo nginx -t && sudo systemctl reload nginx
sudo certbot --nginx -d office-automation.example.gov.hk   # obtains the cert and rewrites the config above
```

Certbot installs a renewal timer automatically (`systemctl list-timers | grep certbot`)
- no manual renewal steps needed.

### Option B: Caddy (automatic HTTPS, less config)

```
# /etc/caddy/Caddyfile
office-automation.example.gov.hk {
    reverse_proxy 127.0.0.1:8000
}
```

Caddy obtains and renews the certificate automatically on `systemctl reload caddy` -
no separate Certbot step.

The application's own security headers (`app.api.main.SecurityHeadersMiddleware`)
still apply behind either proxy; neither needs to duplicate them.

## 6. Cloud server preparation checklist

Generic hardening steps for whichever cloud provider hosts the server,
before pointing DNS at it:

- [ ] Create a non-root user with `sudo`, disable direct root SSH login
- [ ] SSH key-based auth only; disable password auth in `sshd_config`
- [ ] Firewall: allow only 22 (SSH, ideally restricted to known IPs/VPN),
      80 and 443 (reverse proxy); the API's own port (8000) and
      PostgreSQL's port (5432) must **not** be open to the internet -
      both are already bound to loopback-only by default (§2, §4.2)
- [ ] Enable automatic OS security updates (`unattended-upgrades` on Debian/Ubuntu)
- [ ] Point DNS (an A/AAAA record) at the server before running Certbot,
      which validates domain ownership over HTTP
- [ ] Confirm the server's clock is correct/NTP-synced - TOTP-based MFA
      (`docs/SECURITY.md`) depends on accurate time
- [ ] Set up off-server backup storage (§4.5) - e.g. sync `data/backups/`
      to object storage or a separate host on the same schedule

## 7. Bare-metal deployment (alternative to Docker)

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

Both the bare-metal `python -m app.api.main` and the Docker image run a
single uvicorn worker, which is sufficient for a typical office's
concurrent load and keeps the in-memory rate limiter and cached plugin
manager consistent. If you need multiple worker processes (e.g.
`uvicorn app.api.main:app --workers 4`), be aware:

- The `slowapi` rate limiter's default in-memory storage does **not**
  share state across worker processes - each worker enforces its own
  counter, effectively multiplying the configured limit by the worker
  count. For multi-worker deployments, configure a shared backend (Redis)
  via `slowapi`'s `storage_uri` option in `app/api/rate_limit.py`.
- This does not affect account lockout (stored in the database, shared
  correctly across workers) - only the IP-based rate limiter.

### Upgrading (bare metal)

```bash
git pull
source .venv/bin/activate
pip install -r requirements.txt
alembic upgrade head
sudo systemctl restart office-automation-api
```

Always take a backup (`python scripts/backup_db.py`) before running a new
migration.

## 8. Health checks and monitoring

- `GET /health` returns `{"status": "ok", "app": "..."}` - use this for the
  reverse proxy's / load balancer's health check and for an uptime
  monitor. The Docker image also runs this as its own `HEALTHCHECK`
  (visible in `docker compose ps`).
- Application logs: `data/logs/application.log` (structured JSON lines),
  or `docker compose logs -f api` for the Docker deployment (structlog
  prints to stdout too, which Docker captures automatically). The file is
  rotated automatically at 20MB, keeping 10 backups (~200MB max), so it
  will not silently fill the disk on a long-running deployment - it does
  not need a `logrotate` entry of its own.
- The `audit_logs` table is the authoritative record of security-relevant
  events (logins, permission denials, uploads, workflow runs, approvals,
  settings changes) - consider a periodic export
  (`app.core.logging_config.export_logs`) to your office's log retention
  system if one exists.
- PostgreSQL connections are validated with a lightweight liveness check
  before each use and recycled every 30 minutes, so a dropped connection
  (DB restart, failover, an idle timeout from a firewall/NAT between the
  app and a managed database) is transparently replaced instead of
  surfacing as a 500 error on whatever request draws it next. No action
  needed - this is automatic for the `postgresql` backend and does not
  apply to SQLite.

## 9. What this deployment model deliberately does not include

- Built-in TLS termination - use a reverse proxy (§5).
- Built-in horizontal scaling / load balancing across machines - this is
  sized for a single office's document volume, not a multi-tenant SaaS.
- Automatic failover / high availability - if that's required, it belongs
  at the PostgreSQL and reverse-proxy layers, which are standard,
  well-documented problems independent of this application.
- A bundled reverse proxy / TLS service in `docker-compose.yml` - kept
  deliberately out of the compose stack so you can choose nginx, Caddy, or
  your cloud provider's own load balancer/TLS offering without this
  repository dictating one.
