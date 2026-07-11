# Developer Guide

## Local setup

```bash
python3.12 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
python scripts/generate_sample_data.py
alembic upgrade head
```

## Project conventions

- Python 3.12+, full type hints, `from __future__ import annotations`
  everywhere.
- Settings are read once via `app.core.config.get_settings()` (cached);
  never read `os.environ` directly elsewhere.
- Every cross-cutting concern (AI, OCR, PDF, image) is behind a Protocol so
  it can be swapped or mocked in tests without touching call sites.
- Business logic (a workflow) lives in a plugin under `app/plugins/`, never
  in `app/workflow/engine.py` — the engine is workflow-agnostic.
- No workflow, rule, or plugin should hardcode a specific district/estate
  name in Python — those live in `config/rules/*.yaml`.

## Adding a new workflow plugin

1. `app/plugins/<plugin_id>/plugin.py`:

   ```python
   from app.plugins.base import BasePlugin

   class MyWorkflowPlugin(BasePlugin):
       plugin_id = "my_workflow"
       display_name = "My Workflow"
       version = "1.0.0"

       def get_stage_handlers(self):
           return {
               "import": self.stage_import,
               "validate": self.stage_validate,
               # ...only implement the stages you need
           }

       def stage_import(self, context):
           ...

   PLUGIN_CLASS = MyWorkflowPlugin
   ```

2. `config/workflows/my_workflow.yaml`:

   ```yaml
   name: my_workflow
   display_name: "My Workflow"
   plugin: my_workflow
   stages: [import, classify, validate, generate, export, archive, log]
   ```

3. Add `"my_workflow"` to `OAP_ENABLED_PLUGINS` in `.env`.
4. Raise `app.workflow.engine.WorkflowStageError("clear reason")` from any
   stage that needs to halt the pipeline with a user-facing message.

## Testing

```bash
pytest                     # all tests
pytest tests/unit          # fast, no I/O beyond tmp_path
pytest tests/integration   # end-to-end plugin pipeline test
```

`tests/conftest.py` isolates each test into its own scratch data directory
via environment variables and clears the `get_settings()` cache, so tests
never touch your real `./data` directory.

OCR/cloud-AI SDKs are optional extras (`pip install -e ".[ocr]"` etc.) and
are not required to run the test suite — the integration test seeds OCR
text directly rather than invoking PaddleOCR/Tesseract, and
`test_ai_factory.py` only exercises provider selection/validation logic.

## Database migrations

```bash
alembic revision -m "add new_field to documents" --autogenerate
alembic upgrade head
```

## Code quality

```bash
ruff check .
mypy app
black --check .
```

## Directory ownership quick reference

| Directory | Owns |
|---|---|
| `app/core` | settings, DB, models, logging, security |
| `app/ai` | AI provider abstraction |
| `app/ocr` | OCR abstraction |
| `app/pdf_engine`, `app/image_engine` | document content manipulation |
| `app/rules` | YAML rule loading + resolution |
| `app/workflow` | pipeline execution engine |
| `app/plugins` | workflow-specific business logic |
| `app/search` | document search |
| `app/api` | HTTP interface |
| `app/gui` | desktop interface |
