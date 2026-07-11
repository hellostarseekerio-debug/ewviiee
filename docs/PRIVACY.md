# Privacy Guide

The Office Automation Platform is designed **local-first**: by default, no
document, document text, or extracted field ever leaves the machine it runs
on. This document explains exactly what is collected, where it is stored,
when (if ever) data leaves the premises, and what controls an administrator
has over that.

## Default mode is local and private

- The default AI provider is `local` (`OAP_AI_PROVIDER=local`), which talks
  to a self-hosted LLM endpoint (e.g. Ollama) on the office's own network -
  nothing is sent to a third party.
- Cloud AI providers (OpenAI, Anthropic, Azure OpenAI) are **disabled by
  default** at a second, independent layer: the `allow_cloud_ai` system
  setting (`app.core.system_settings`) defaults to `false` regardless of
  which provider is configured in `.env`. An **administrator** must
  explicitly enable it (Settings screen in the GUI, or `PUT /api/settings`)
  before a single byte of document text can reach a cloud provider - see
  `app/ai/factory.py::get_guarded_ai_provider`.
- AI is only ever consulted as a fallback when the deterministic rule
  engine (`config/rules/*.yaml`) cannot resolve a field (e.g. an estate
  name). Most documents never invoke AI at all.
- The database defaults to a local SQLite file (`./data/office_automation.db`).
  Nothing about this application requires internet access to function.

## What is stored, and where

| Data | Table / location | Purpose |
|---|---|---|
| Document metadata (district, estate, title, politician, dates, filename) | `documents` | Search, reporting, workflow tracking |
| Full OCR text of processed documents | `documents.ocr_text` | Search, field extraction |
| Generated output files and all prior versions | `data/archive/`, `data/export/`, `document_versions` | Version history / rollback |
| User accounts (username, full name, role, hashed password) | `users` | Authentication and RBAC. Passwords are bcrypt hashes - never recoverable, never logged. |
| Login attempts, permission denials, uploads, workflow runs, approvals, rollbacks, deletions | `audit_logs` | Accountability / incident investigation |
| AI provider calls | `ai_usage_logs` | **Metadata only** - provider name, operation, timing, success/failure. The prompt, the document text, and the AI's response are deliberately never written here. |
| Admin-configured runtime settings (e.g. the cloud-AI switch) | `system_settings` | So a policy change takes effect immediately |

Nothing beyond what's in this table is collected. There is no telemetry,
no analytics, no phone-home behavior, and no third-party tracking of any
kind built into this application.

## When data can leave the premises

Only one path: if an administrator has explicitly enabled `allow_cloud_ai`
**and** configured a cloud provider (`OAP_AI_PROVIDER=openai` /
`anthropic` / `azure_openai` plus its API key), then the specific text
passed to `AIProvider.classify()` / `.extract_fields()` (a short snippet of
OCR'd document text, not the whole document file) is sent to that
provider's API for that one call. Every such call is logged (see
`ai_usage_logs` above) so cloud usage is always auditable, but the log
itself never stores what was sent.

No other network calls are made by the core platform. (Optional cloud
storage import sources - Dropbox/Google Drive/OneDrive - are opt-in via
`.env` and only used if an admin configures a root path for them.)

## User consent and settings controls

- The Settings screen's **Privacy** section shows the current cloud-AI
  state and lets an Administrator toggle it, with an explicit warning
  dialog on enabling it.
- Because enabling cloud AI is an administrative, office-wide policy
  decision (not a per-document choice), the platform does not implement a
  per-user consent prompt per document - it implements a coarser, safer
  control: cloud AI is either off for the whole office, or on. If per-case
  consent is required by your office's privacy policy, keep cloud AI
  disabled and rely on the rule engine + local AI, or add a manual review
  gate (`stage_config.review.require_manual_review: true` in a workflow's
  YAML) before export.

## Data retention and deletion

- `SystemSetting` key `data_retention_days` (default 365) documents the
  office's intended retention policy; enforcing automated purging beyond
  that period is left to the administrator's backup/retention procedure
  (see `docs/admin_guide.md`) since a government office's actual legal
  retention requirements vary by document type and should be reviewed
  before automating deletion.
- Deletion via the API/GUI is **soft delete only** (`documents.is_deleted`)
  - the record and its audit trail are retained but excluded from
  search/listing. This is deliberate: a government office needs to be able
  to prove what happened to a document even after someone asked for it to
  be "deleted" from daily use. If your office's data protection obligations
  require true erasure after a retention period, that must be a deliberate,
  logged, administrator-run purge - not an accidental one-click action -
  and is intentionally not exposed as a casual button in this build.

## Recommendations for the office's Data Protection Officer / IC (Hong Kong PDPO)

- Complete `docs/PRIVACY_POLICY_TEMPLATE.md` with the office's actual
  retention periods, contact details, and legal basis before deploying to
  real constituent data.
- Keep `allow_cloud_ai` disabled unless a specific workflow genuinely
  requires it and the office has confirmed the chosen provider's data
  handling terms are acceptable for constituent data.
- Review `docs/DATA_HANDLING.md` for the technical detail behind this
  document.
