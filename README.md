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
  api/         FastAPI backend (auth, documents, search, workflows, plugins)
  gui/         PySide6 desktop shell (dashboard, explorer, workflow manager, search, logs, settings)
config/
  rules/       districts.yaml, estates.yaml, aliases.yaml, validation.yaml, naming.yaml, poster_mappings.yaml
  workflows/   housing_estate_poster.yaml (and future workflow definitions)
alembic/       database migrations
tests/
  unit/        rule engine, workflow engine, PDF engine, AI factory
  integration/ end-to-end Housing Estate Poster pipeline test
sample_data/   generated sample poster + application PDF for demos
docs/          architecture, developer guide, admin guide, user manual, API docs
scripts/       sample data generator, Windows/macOS build scripts
```

## Quick start

```bash
python3.12 -m venv .venv
source .venv/bin/activate          # .venv\Scripts\activate on Windows
pip install -r requirements.txt
cp .env.example .env

# Generate demo assets (a poster image + application PDF)
python scripts/generate_sample_data.py

# Apply database migrations
alembic upgrade head

# Run the API
python -m app.api.main
# -> http://localhost:8000/docs (interactive Swagger UI)

# Run the desktop GUI
python -m app.gui.main
```

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

- [Architecture](docs/architecture.md)
- [Developer Guide](docs/developer_guide.md)
- [Administrator Guide](docs/admin_guide.md)
- [User Manual](docs/user_manual.md)
- [API Reference](docs/api.md)

## Security

Local-first by default (SQLite, no external calls unless a cloud AI
provider is explicitly configured). Every action is written to the audit
log. Secrets are encrypted at rest via `app/core/security.py`. Role-based
permissions (`admin` / `editor` / `reviewer` / `viewer`) gate API access.

## Status

This is the initial production-ready core: workflow engine, plugin system,
rule engine, AI/OCR/PDF/image engines, FastAPI backend, PySide6 desktop
shell, and the fully working Housing Estate Poster workflow, with unit and
integration test coverage. Signed Windows `.exe` / macOS `.app` installers
require a per-platform build step — see `scripts/build_windows.py` and
`scripts/build_macos.py`.
