# Administrator Guide

## Configuration

All runtime configuration lives in `.env` (copy from `.env.example`) or
environment variables prefixed `OAP_`. See `app/core/config.py` for the
authoritative list of settings and defaults.

### Switching AI provider

Set `OAP_AI_PROVIDER` to one of `openai`, `anthropic`, `azure_openai`,
`local`, and fill in the matching credential variables. No restart-time code
change is required — this is a configuration-only switch.

### Switching database backend

- SQLite (default, zero setup): `OAP_DATABASE_BACKEND=sqlite`,
  `OAP_SQLITE_PATH=./data/office_automation.db`
- PostgreSQL: `OAP_DATABASE_BACKEND=postgresql`,
  `OAP_POSTGRES_DSN=postgresql+psycopg2://user:pass@host:5432/dbname`, and
  `pip install -e ".[postgres]"`

Run `alembic upgrade head` after changing the backend to create the schema.

## Managing rules

Edit the YAML files under `config/rules/`:

- `districts.yaml` — district id/name/aliases
- `estates.yaml` — estate id/name/district_id/aliases
- `aliases.yaml` — free-form OCR-noise normalization
- `validation.yaml` — required fields, patterns, date formats
- `naming.yaml` — output filename pattern + output folder routing
- `poster_mappings.yaml` — page/poster slot mappings

Changes take effect on the next document processed — no restart required
for the CLI/API workers picking up a fresh `RuleEngine`; the desktop GUI's
Workflow Manager screen has a manual "Refresh" button.

## Managing plugins

Enable/disable a workflow by editing `OAP_ENABLED_PLUGINS` (a JSON list),
e.g. `OAP_ENABLED_PLUGINS=["housing_estate_poster","banner_applications"]`.
Disabling a plugin here removes it from the Workflow Manager and
`/api/workflows` without deleting its code or configuration.

## User management and roles

Roles, lowest to highest privilege: `viewer`, `reviewer`, `editor`, `admin`.

- The **first** account in a fresh database can self-register via
  `POST /api/auth/users` and is always forced to `admin` regardless of the
  requested role - this is the one-time bootstrap path.
- Every account after that must be created by an authenticated admin via
  `POST /api/auth/admin/users`, or (recommended, since it never touches the
  network) by running `python scripts/create_admin.py --username <name>
  --role <role>` directly on the server.
- Passwords must be 12+ characters with upper/lower/digit/special
  character. Accounts lock for 15 minutes after 5 consecutive failed
  logins.
- Role checks are enforced per-endpoint via `app.api.deps.require_role`
  and mirrored in the desktop GUI (see `docs/SECURITY.md` for the full
  permission matrix).

## Privacy controls

The cloud-AI kill switch (`allow_cloud_ai`, default **off**) lives in the
`system_settings` table and can be changed live from the GUI's
Settings → Privacy screen (admin only) or via `PUT /api/settings`. See
`docs/PRIVACY.md` for exactly what is/isn't sent when it's enabled.

## Approval workflow, version history, and rollback

Every processed document starts `approval_status=pending`. A Reviewer (or
above) approves or rejects it from the GUI's Review screen or
`POST /api/documents/{id}/approve` / `/reject`. Every generated output is
recorded as an immutable `DocumentVersion` (with a SHA-256 checksum) - the
original source file is never modified. An Editor (or above) can restore
an earlier version via the GUI or `POST /api/documents/{id}/rollback`,
which copies that version's file forward as a new version rather than
overwriting anything.

## Backups

**Bare-metal (SQLite) deployment**: run `python scripts/backup_db.py` on a
schedule (daily is recommended) - it backs up the SQLite file plus
`data/archive/` and `data/export/` into a single timestamped `.tar.gz`
under `Settings.backup_dir`, and prunes backups older than
`backup_retention_days` (default 90). Restore with
`python scripts/restore_db.py <backup_file>`.

**Docker Compose (PostgreSQL) deployment**: run
`bash scripts/docker_backup_postgres.sh` on a schedule instead - it runs
`pg_dump` inside the `db` container and archives `data/archive`/`export`/`import`
on the host. Restore with `bash scripts/docker_restore_postgres.sh <dump> <files-archive>`.
See `docs/DEPLOYMENT.md` §4.5 for the full walkthrough.

Both restore scripts always take a fresh safety backup of the current
state before overwriting anything, and prompt for confirmation unless
`--yes` is passed.

## Logs and audit trail

- Structured application logs: `data/logs/application.log`
- Per-document processing history: `processing_events` table
- Full audit trail: `audit_logs` table (actor, action, resource, success)
- Export logs from the GUI's Logs screen, or call
  `app.core.logging_config.export_logs(destination)` directly.

## Troubleshooting

See `docs/TROUBLESHOOTING.md` for the full guide. Quick reference:

| Symptom | Likely cause | Fix |
|---|---|---|
| Workflow halts at `extract` with missing district/estate | OCR text too noisy or alias not configured | Add an alias in `config/rules/aliases.yaml` or `estates.yaml` |
| OCR confidence always low | PaddleOCR/Tesseract not installed, or scan quality poor | `pip install -e ".[ocr]"`; check `OAP_OCR_CONFIDENCE_THRESHOLD` |
| AI provider errors on startup | Missing API key/endpoint for the selected provider | Check `.env` values match `app/ai/factory.py` requirements |
| Workflow not visible in GUI/API | Plugin not in `OAP_ENABLED_PLUGINS`, or YAML missing under `config/workflows/` | Verify both files exist and plugin id matches |
| "Path is outside all permitted import roots" | Client passed a path outside the approved import/archive/export roots | Move the file into an approved root, or use `POST /api/documents/upload` |
| Account locked | 5 consecutive failed logins | Wait 15 minutes, or reset via `scripts/create_admin.py` |
