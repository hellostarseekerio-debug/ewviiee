# Troubleshooting Guide

## Installation / startup

**"OAP_SECRET_KEY is still the insecure default" on startup**
You set `OAP_ENVIRONMENT=production` without setting a real
`OAP_SECRET_KEY`/`OAP_ENCRYPTION_KEY`. See `docs/INSTALLATION.md` step 2.
This check exists specifically so the platform can't accidentally go live
with the shipped defaults.

**`alembic upgrade head` fails with "no such table"**
Make sure `OAP_SQLITE_PATH` (or `OAP_POSTGRES_DSN`) in `.env` points at
where you expect the database to live, and that the directory is
writable. Alembic reads the same `Settings.database_url` the app uses.

**GUI fails to start with a Qt/EGL/OpenGL error on Linux**
Install the platform's OpenGL/XCB libraries, e.g. on Debian/Ubuntu:
```bash
sudo apt install libegl1 libxcb-cursor0
```
On a headless server, run with `QT_QPA_PLATFORM=offscreen` for testing
only - the GUI is meant for desktop use, not headless servers (use the API
instead).

**`bcrypt`/`passlib` error: "password cannot be longer than 72 bytes" even for short passwords**
This is a known incompatibility between `passlib==1.7.4` and
`bcrypt>=4.1` (the newer `bcrypt` removed the `__about__` module
`passlib` probes to detect its version, which breaks passlib's internal
self-test). `requirements.txt`/`pyproject.toml` pin `bcrypt==4.0.1` to
avoid this - if you still hit it, check `pip show bcrypt` and reinstall
the pinned version.

## Login / accounts

**"Account is temporarily locked"**
5 consecutive failed logins lock an account for 15 minutes. Wait, or have
an administrator run `scripts/create_admin.py --username <user> --role
<role>` to reset the password (this also clears the lockout).

**Can't create a second admin / "User creation requires an authenticated administrator"**
This is intentional (see `docs/SECURITY.md`). Log in as the existing
admin and use `POST /api/auth/admin/users`, or run
`scripts/create_admin.py` on the server.

## Document processing

**A document fails at the "validate" stage**
The error message names the missing/invalid field (e.g. "Missing required
field: estate"). This usually means OCR could not read the source clearly
enough, or the estate/district/alias isn't in `config/rules/*.yaml` yet -
add it there (no code change needed) and re-run.

**"Path is outside all permitted import roots"**
The workflow only accepts documents under `local_import_root`,
`archive_root`, `export_root`, or a configured Dropbox/Google
Drive/OneDrive root (`app.workflow.runner.allowed_import_roots`). Move the
file into one of those, or upload it via `POST /api/documents/upload`
which stores it under `local_import_root` automatically.

**OCR confidence always low / OCR step fails**
Install the optional OCR extras (`pip install -e ".[ocr]"`) and, for the
Tesseract fallback, the Tesseract binary itself (see
`docs/INSTALLATION.md` prerequisites). Check
`OAP_OCR_CONFIDENCE_THRESHOLD` isn't set unrealistically high for your
scan quality.

**AI fallback isn't working / always returns nothing**
By design - cloud AI providers are disabled until an administrator
explicitly enables `allow_cloud_ai` in Settings (see `docs/PRIVACY.md`).
The local provider (`OAP_AI_PROVIDER=local`) needs a reachable endpoint at
`OAP_LOCAL_LLM_BASE_URL` (e.g. a running Ollama instance) - if that's not
running, the rule engine logs a warning and simply proceeds without AI
assistance rather than failing the whole document.

## API

**429 Too Many Requests**
Rate limiting kicked in (`OAP_RATE_LIMIT_LOGIN` / `OAP_RATE_LIMIT_DEFAULT`).
This is expected under repeated rapid requests (including from automated
tests hitting a shared endpoint) - wait for the window to reset, or raise
the limit in `.env` for a trusted internal deployment.

**CORS errors in a browser client**
Set `OAP_CORS_ALLOWED_ORIGINS` to the exact origin your client is served
from (protocol + host + port). Wildcard `*` is rejected in production.

## Backups

**Restoring from a backup (bare-metal / SQLite)**
```bash
python scripts/restore_db.py data/backups/backup_<timestamp>.tar.gz
```
Takes a safety backup of the current state first, prompts for
confirmation (add `--yes` to skip it), then restores the database and
`data/archive`/`data/export`. Restart the API/GUI afterward.

**Restoring from a backup (Docker Compose / PostgreSQL)**
```bash
bash scripts/docker_restore_postgres.sh data/backups/postgres_<timestamp>.dump data/backups/files_<timestamp>.tar.gz
```
Same safety-backup-first behavior. See `docs/DEPLOYMENT.md` §4.5 for the
full walkthrough.
