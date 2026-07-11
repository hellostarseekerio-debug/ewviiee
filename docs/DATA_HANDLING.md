# Data Handling Reference

Technical companion to `docs/PRIVACY.md` - the exact tables, columns, and
code paths that touch document content and personal data. Intended for
developers and IT auditors.

## Data flow through a workflow run

```
source file (local disk / Dropbox / Google Drive / OneDrive root)
    │
    ▼  (path validated against allowed roots - app.core.file_safety.resolve_within_root)
Workflow Engine (app/workflow/engine.py)
    │
    ▼  each stage handler supplied by the plugin (app/plugins/<id>/plugin.py)
Document + ProcessingEvent + DocumentVersion rows (app/workflow/runner.py)
    │
    ▼
SQLite/PostgreSQL (app/core/database.py)
```

At no point in this flow is a document sent anywhere over the network
unless the `extract` stage falls back to AI (see below) or an explicit
cloud import source is configured.

## Where personal/constituent data lives

- `documents.politician`, `documents.district`, `documents.estate`,
  `documents.ocr_text`, `documents.extracted_fields` (JSON) - all derived
  from the source document content.
- `document_versions.file_path` - points at generated PDF files on local
  disk (`data/archive/`, `data/export/`, `data/working/`); the files
  themselves are not duplicated into the database.
- `users` - office staff accounts only (not constituent data): username,
  optional full name, bcrypt password hash, role.

## AI call data path

`app.ai.factory.get_guarded_ai_provider()` is the single choke point. It:

1. Reads `Settings.ai_provider`. If it names a cloud provider
   (`app.ai.factory.is_cloud_provider`), it checks the DB-backed
   `allow_cloud_ai` setting (`app.core.system_settings`).
2. Refuses (returns `None`) if cloud AI is not explicitly enabled - the
   caller (the rule engine) then simply proceeds without AI assistance,
   it does not error out.
3. If allowed, wraps the provider in `LoggingAIProvider`, which records
   provider/operation/timing/success to `ai_usage_logs` on every call and
   **never** touches the actual prompt or response text in that log.

The rule engine (`app/rules/engine.py`) only ever calls AI with a short
text snippet relevant to the specific field being resolved (e.g. the OCR
text of one poster), not the entire source file, and only as a fallback
after every configured alias/pattern match has failed.

## Retention and export

- `scripts/backup_db.py` backs up the database file plus `data/archive/`
  and `data/export/` into a single timestamped `.tar.gz`, and prunes
  backups older than `Settings.backup_retention_days` (default 90 days -
  this governs *backup* retention, distinct from the
  `data_retention_days` system setting which documents the office's
  intended retention policy for the live data itself).
- Logs are exportable via the GUI's Logs screen or
  `app.core.logging_config.export_logs()`, combining the structured
  application log with a plain-text dump of the `audit_logs` table.

## Columns that must never be added without a privacy review

If you extend this platform, avoid persisting: raw uploaded file bytes
inside a database column (files belong on disk/object storage, referenced
by path - keeps backup/retention/access-control simple and consistent),
AI prompts/responses in `ai_usage_logs`, or plaintext passwords/API keys
anywhere. `SecretBox` (`app.core.security`) exists for any future
credential that must be stored in the database.
