# Office Automation Platform

An enterprise-grade AI document automation platform for a Hong Kong
Legislative Council office. It imports, classifies, OCRs, extracts,
validates, generates, exports, archives and makes searchable any office
document — through **configurable workflows** rather than one-off scripts.

The **Housing Estate Poster Applications** workflow ships as the first
built-in plugin. Every future office workflow (Banner Applications,
Government Forms, Press Releases, ...) is added the same way: a plugin
package + a YAML workflow definition, with **zero changes to core code**.

## Why this architecture

| Concern | Approach |
|---|---|
| Adding a new workflow | Drop a plugin under `app/plugins/<name>/` + a YAML file under `config/workflows/` |
| Changing estate/district mappings | Edit `config/rules/*.yaml` — no code, no redeploy |
| Switching AI provider | Set `OAP_AI_PROVIDER` (openai / anthropic / azure_openai / local) |
| Switching database | Set `OAP_DATABASE_BACKEND` (sqlite / postgresql) |
| Auditability | Every workflow stage writes a `ProcessingEvent` + structured log + `AuditLog` row |

## Repository layout

```
app/
  core/        settings, DB session, ORM models, logging, security
  ai/          AI provider abstraction (OpenAI/Anthropic/Azure/local) + factory
  ocr/         PaddleOCR primary + Tesseract fallback, confidence-based retry
  pdf_engine/  text/image replace, merge/split/insert/delete/rotate/compress/forms
  image_engine/ resize/crop/align/optimize/validate/preview
  rules/       YAML-driven rule engine (districts, estates, aliases, validation, naming)
  workflow/    configurable stage pipeline engine + YAML workflow loader
  plugins/     plugin interface + manager + housing_estate_poster plugin
  search/      multi-field document search
  api/         FastAPI backend (auth+RBAC, documents/upload/review, search, workflows, plugins, settings)
  gui/         PySide6 desktop shell (login, dashboard, explorer, workflow manager, review, search, logs, settings)
config/
  rules/       districts.yaml, estates.yaml, aliases.yaml, validation.yaml, naming.yaml, poster_mappings.yaml
  workflows/   housing_estate_poster.yaml (and future workflow definitions)
alembic/       database migrations
tests/
  unit/        rule engine, workflow engine, PDF engine, AI factory, account security, AI privacy guard
  integration/ end-to-end Housing Estate Poster pipeline, review/versioning/rollback
  security/    RBAC, path traversal, malicious upload, auth requirement tests
sample_data/   generated sample poster + application PDF for demos
docs/          installation, architecture, developer/admin guides, user manual, API docs, security, privacy
scripts/       sample data generator, admin bootstrap, DB backup, Windows/macOS build scripts
```

## Quick start

```bash
python3.12 -m venv .venv
source .venv/bin/activate          # .venv\Scripts\activate on Windows
pip install -r requirements.txt
cp .env.example .env
# Edit .env: set OAP_SECRET_KEY and OAP_ENCRYPTION_KEY (see docs/INSTALLATION.md)

# Apply database migrations
alembic upgrade head

# Create the first administrator account (never over the network)
python scripts/create_admin.py --username admin --full-name "Jane Doe"

# Generate demo assets (a poster image + application PDF)
python scripts/generate_sample_data.py

# Run the API
python -m app.api.main
# -> http://localhost:8000/docs (interactive Swagger UI)

# Run the desktop GUI
python -m app.gui.main
```

Full walkthrough: [docs/INSTALLATION.md](docs/INSTALLATION.md).

### Or: Docker Compose (API + PostgreSQL, for a server deployment)

```bash
cp .env.docker.example .env
# Edit .env: set POSTGRES_PASSWORD, OAP_SECRET_KEY, OAP_ENCRYPTION_KEY, OAP_CORS_ALLOWED_ORIGINS

docker compose build
docker compose up -d
docker compose exec api python scripts/create_admin.py --username admin --full-name "Jane Doe"
```

Full walkthrough (server requirements, HTTPS, backups): [docs/DEPLOYMENT.md](docs/DEPLOYMENT.md).

### Optional heavy dependencies

OCR and cloud AI SDKs are optional extras so the core install stays light:

```bash
pip install -e ".[ocr]"           # PaddleOCR + Tesseract bindings
pip install -e ".[ai-openai]"     # OpenAI SDK
pip install -e ".[ai-anthropic]"  # Anthropic SDK
pip install -e ".[postgres]"      # PostgreSQL driver
```

Tesseract itself (the binary, not just the Python bindings) must be
installed separately via your OS package manager for the fallback OCR
engine to work.

## Running tests

```bash
pip install -r requirements.txt
pytest
```

## Adding a new workflow (e.g. "Banner Applications")

1. Create `app/plugins/banner_applications/plugin.py` implementing the
   `Plugin` protocol (`app/plugins/base.py`) — supply stage handlers for
   whichever of the 11 pipeline stages you need.
2. Create `config/workflows/banner_applications.yaml` describing the stage
   order and per-stage configuration.
3. Add `"banner_applications"` to `OAP_ENABLED_PLUGINS`.
4. Add any new district/estate/validation/naming rules to
   `config/rules/*.yaml` if the workflow needs them.

No other file changes are required — the Workflow Manager screen and the
`/api/workflows` endpoint pick up the new workflow automatically.

## Documentation

- [Installation Guide](docs/INSTALLATION.md)
- [Production Deployment Guide](docs/DEPLOYMENT.md) (Docker Compose + PostgreSQL, or bare metal)
- [Architecture](docs/architecture.md)
- [Developer Guide](docs/developer_guide.md)
- [Administrator Guide](docs/admin_guide.md)
- [User Manual](docs/user_manual.md)
- [API Reference](docs/api.md)
- [Security Guide](docs/SECURITY.md)
- [Privacy Guide](docs/PRIVACY.md)
- [Data Handling Reference](docs/DATA_HANDLING.md)
- [Privacy Policy Template](docs/PRIVACY_POLICY_TEMPLATE.md)
- [Troubleshooting](docs/TROUBLESHOOTING.md)

## Security & privacy

Local-first by default: SQLite, no external network calls, and cloud AI
providers are refused until an administrator explicitly enables them
(`allow_cloud_ai`, off by default) — see `docs/PRIVACY.md`. Every action
(login, upload, workflow run, approval, rollback, deletion, settings
change) is written to the audit log. Passwords are bcrypt-hashed with a
12+ character policy and account lockout after 5 failed attempts.
Role-based permissions (`admin` / `editor` / `reviewer` / `viewer`) gate
every API endpoint and are mirrored in the desktop GUI. File uploads are
validated by extension, size, and magic-byte signature, and every
client-supplied path is checked against approved import roots to prevent
path traversal. Full detail in `docs/SECURITY.md`.

## Status

Production-hardened core: workflow engine, plugin system, rule engine,
AI/OCR/PDF/image engines, FastAPI backend (RBAC, rate limiting, security
headers, audit logging), PySide6 desktop shell (with login, RBAC-gated
actions, and a live dashboard/review queue), and the fully working Housing
Estate Poster workflow with approval + version history + rollback. 66
unit/integration/security tests pass. Signed Windows `.exe` / macOS `.app`
installers require a per-platform build step — see
`scripts/build_windows.py` and `scripts/build_macos.py`.
