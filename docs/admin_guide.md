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
Create a user via `POST /api/auth/users` (see `docs/api.md`). Role checks
are enforced per-endpoint via `app.api.deps.require_role`.

## Backups

Configure `OAP_BACKUP_DIR` / retention via `Settings.backup_dir` and
`backup_retention_days`. Back up the SQLite file (or run `pg_dump` for
PostgreSQL) plus the `data/archive` and `data/export` directories on the
same schedule — those directories hold the durable output artifacts.

## Logs and audit trail

- Structured application logs: `data/logs/application.log`
- Per-document processing history: `processing_events` table
- Full audit trail: `audit_logs` table (actor, action, resource, success)
- Export logs from the GUI's Logs screen, or call
  `app.core.logging_config.export_logs(destination)` directly.

## Troubleshooting

| Symptom | Likely cause | Fix |
|---|---|---|
| Workflow halts at `extract` with missing district/estate | OCR text too noisy or alias not configured | Add an alias in `config/rules/aliases.yaml` or `estates.yaml` |
| OCR confidence always low | PaddleOCR/Tesseract not installed, or scan quality poor | `pip install -e ".[ocr]"`; check `OAP_OCR_CONFIDENCE_THRESHOLD` |
| AI provider errors on startup | Missing API key/endpoint for the selected provider | Check `.env` values match `app/ai/factory.py` requirements |
| Workflow not visible in GUI/API | Plugin not in `OAP_ENABLED_PLUGINS`, or YAML missing under `config/workflows/` | Verify both files exist and plugin id matches |
