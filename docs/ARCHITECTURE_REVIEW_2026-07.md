# Architecture Review & Implementation Plan — Document Management Upgrade

**Status:** Draft for approval. No code changes included in this document.
**Scope:** Turn the current Poster Archive / Document Automation platform into
a polished, production-ready internal document management system for a
Hong Kong Legislative Council office, per the requirements list supplied.

---

## 1. Current Architecture — What Actually Exists Today

### 1.1 Backend (`app/`)

| Layer | Location | Notes |
|---|---|---|
| ORM models | `app/core/models.py` | `Document`, `ProcessingEvent`, `DocumentVersion`, `WorkflowRun`, `User`, `SystemSetting`, `AIUsageLog`, `AuditLog`, `Poster` |
| DB migrations | `alembic/versions/0001`–`0005` | Sequential, no branches |
| API routes | `app/api/routes/*.py` | `auth`, `documents`, `posters`, `search`, `dashboard`, `workflows`, `plugins`, `settings` |
| Rule engine | `app/rules/engine.py`, `fuzzy.py`, `schema.py` | YAML-driven district/estate alias + fuzzy matching, AI fallback only if a provider is configured (none is, by default) |
| Workflow engine | `app/workflow/engine.py`, `runner.py`, `stages.py`, `loader.py` | Generic staged pipeline; **only one plugin exists** (`housing_estate_poster`) |
| AI abstraction | `app/ai/*.py` | Protocol-based (`AIProvider`), OpenAI/Anthropic/Azure/local providers, `RuleEngine`'s fallback path only |
| Poster parser | `app/posters/parser.py` | Regex-based, just fixed for the block-association bug |
| Search | `app/search/query.py` | `Document`-only filtered query builder; **Posters has its own separate, duplicate filter logic in `posters.py`** |
| File safety | `app/core/file_safety.py` | Extension/size/magic-byte validation, path-traversal guards |

### 1.2 Frontend (`frontend/`)

Next.js 15 App Router, React 19, Tailwind v4, hand-built shadcn-style components.

| Page | File | State |
|---|---|---|
| Dashboard | `app/(app)/dashboard/page.tsx` | Document/user/AI-usage stats only — **no poster stats** |
| Documents list | `app/(app)/documents/page.tsx` | Flat table, single free-text search, no bulk actions, no folder view |
| Document detail | `app/(app)/documents/[id]/page.tsx` | Shows metadata + version history, no rich preview |
| Poster Archive | `app/(app)/posters/page.tsx` | Table/Card toggle, filters, CSV export, bulk delete, paste-import dialog |
| Search | `app/(app)/search/page.tsx` | Document-only advanced search |
| Settings | `app/(app)/settings/page.tsx` | Profile/Security/Preferences/Org tabs |

### 1.3 Storage model

Files sit under four **flat** configured roots (`local_import_root`,
`archive_root`, `export_root`, optional Dropbox/Drive/OneDrive sync roots).
`config/rules/naming.yaml` maps a workflow category to **one flat folder
name** (e.g. `HousingEstatePosters/`) and a filename pattern
(`{district}_{estate}_{version}_{date}`). There is **no nested hierarchy**
(Year/Month/District/Estate does not exist anywhere in the codebase) and
**no ZIP export capability anywhere** (`grep -rl zipfile app/` returns nothing).

### 1.4 Status / workflow model

Two independent status concepts already exist:
- `DocumentStatus` (imported → classified → ocr_done → extracted → validated
  → generated → review → exported → archived / failed) — a **pipeline**
  status, already fairly rich.
- `ApprovalStatus` (pending / approved / rejected) — a **review** status,
  shared by both `Document` and `Poster`.

The "replace the current Pending" ask is about `Poster.approval_status`:
today every imported poster is stuck at `pending` with no way to move it
through a real lifecycle (e.g. drafted → pending review → approved →
published to Dropbox → archived/expired). This is a **product gap, not a
bug** — the field exists, but the workflow around it doesn't.

### 1.5 What's genuinely missing (confirmed by grep/read, not assumed)

- No folder hierarchy generation (Year/Month/District/Estate) — **new**.
- No ZIP download of any kind — **new**.
- No document-level duplicate detection (Poster dedupes only by exact
  Dropbox URL; `Document` has a `checksum_sha256` column on *versions* only,
  never compared against other documents at upload time) — **new**.
- No system-wide activity feed UI (audit log exists in DB + dashboard's
  "recent activity" list, but nothing dedicated/filterable) — **partial, needs UI**.
- No in-browser document preview (PDF/image viewer) — **new**.
- Two parallel, duplicated search implementations (`app/search/query.py` for
  Documents, ad hoc filtering inline in `posters.py` for Posters) — **tech debt**.
- Poster and Document are entirely separate tables/pages with no shared
  "unified document" concept, which will matter once posters get real
  files (not just Dropbox links) and folder placement.

---

## 2. Key Architectural Decision: Unify Poster and Document, or Keep Them Separate?

This is the single biggest fork in the road and everything else in this
plan depends on the answer, so I want to flag it before laying out phases.

**Option A — Keep them separate** (lower risk, less rework): `Poster` stays
a lightweight "reference to a Dropbox link" record; folder hierarchy, ZIP
export, and status workflow are all built as generic, reusable services that
both `Document` and `Poster` opt into via a shared interface, but the two
tables/pages remain distinct.

**Option B — Merge into one polymorphic `Document`** (larger rework,
cleaner long-term): migrate `Poster` rows into `Document` with a
`document_type = "poster"` discriminator, so there is one search index, one
folder/ZIP system, one status workflow, one activity feed, for real.

**Recommendation: Option A now, with the shared services built so Option B
is a pure data-migration later if you ever want it.** Reasons:
- Posters are literally *links to files this platform doesn't own* — no
  local `source_path`, no OCR, no PDF generation for most of them. Forcing
  that into `Document`'s pipeline-oriented schema (`ocr_confidence`,
  `output_path`, `archive_path`, etc., all of which assume a file this
  system generated) would mean adding a lot of "N/A for posters" columns.
  This project's own conventions (docstrings in `models.py`, `parser.py`)
  already made this call deliberately — reversing it should be a conscious
  choice, not a side effect of an unrelated feature request.
- A merge is a real data migration with rollback risk, for a HK-government
  production system, for no immediate functional gain — everything you
  asked for (hierarchy, ZIP, status, dedup, search, preview) can be built
  generically and shared without merging tables.
- If you later decide you *do* want one unified inbox, the shared-service
  design below means the migration is "move data," not "rewrite features."

I'll proceed on this basis unless you tell me otherwise — flagging it now
because it's the one decision that's expensive to reverse later.

---

## 3. Proposed New Backend Modules

| New module | Purpose |
|---|---|
| `app/storage/hierarchy.py` | Pure function(s): `(year, month, district, estate) -> Path`, given a configurable pattern (default `{year}/{month:02d}/{district}/{estate}`). Used by both the folder-organizer job and the ZIP builder — single source of truth for path shape. |
| `app/storage/archive_zip.py` | Builds a ZIP stream on the fly (no temp file for small sets; streamed temp file for large ones) preserving the hierarchy from `hierarchy.py`, for a given set of Document/Poster IDs or a filter. |
| `app/dedup/duplicate_detector.py` | Content-hash (sha256) + fuzzy near-duplicate (perceptual hash for images, normalized-title similarity for posters) detection, run at import/upload time and as an on-demand "find existing duplicates" scan. |
| `app/search/unified.py` | Thin common layer so Document and Poster search share one filter-building/pagination implementation instead of two hand-rolled ones (removes today's duplication in `posters.py` vs `query.py`). |
| `app/api/routes/activity.py` | Dedicated, filterable activity/audit feed endpoint (the DB table and dashboard snippet already exist; this exposes it properly with pagination/filters instead of a hardcoded `limit(20)`). |

## 4. Backend Files That Change

| File | Change |
|---|---|
| `app/core/models.py` | New `PosterStatus` enum (replacing bare `ApprovalStatus` reuse for posters) with a real lifecycle; new `folder_path` column on `Poster`/`Document`; new `content_hash` column for dedup; new `DuplicateMatch` table (or reuse `AuditLog`-style side table) |
| `alembic/versions/0006_*.py` | New migration(s) — see §6 |
| `app/api/schemas.py` | New/changed Pydantic schemas: `PosterStatus`, ZIP export request, dedup response, activity feed response |
| `app/api/routes/posters.py` | New endpoints: status transition, ZIP export, duplicate check/merge; folder-path computed on create/update |
| `app/api/routes/documents.py` | New endpoints: ZIP export, duplicate check; bulk-action endpoints (bulk approve/reject/status-change/delete — bulk delete exists for posters only today) |
| `app/api/routes/search.py` | Extended filters (status, folder path, has-duplicate) |
| `app/api/routes/dashboard.py` | Add poster stats, storage stats, duplicate-count widget data |
| `app/api/routes/activity.py` (new) | Activity feed with pagination/filtering |
| `app/posters/parser.py` | Populate `content_hash`/dedup signal at parse time (hook only — detection logic lives in `app/dedup/`) |
| `app/rules/engine.py` | No functional change required, but its district/estate lists become the folder-hierarchy source of truth — worth a comment/doc update |
| `config/rules/naming.yaml` | New `folder_hierarchy_pattern` key |
| `app/core/config.py` | New settings: `folder_hierarchy_pattern`, `zip_export_max_files`/`max_bytes` (DoS guard), `duplicate_detection_enabled` |

## 5. Frontend Files That Change / Are Added

| File | Change |
|---|---|
| `frontend/lib/api/types.ts`, `endpoints.ts` | New types/calls for ZIP export, status transitions, duplicates, activity feed, dashboard additions |
| `frontend/components/documents/status-badge.tsx` | Extend for new `PosterStatus` lifecycle (currently only `DocumentStatus`/`ApprovalStatus`) |
| `frontend/app/(app)/posters/page.tsx` | Add: bulk status change, ZIP-download button (selection or filtered set), duplicate warnings inline, folder-path column |
| `frontend/app/(app)/documents/page.tsx` | Add: bulk actions toolbar (approve/reject/delete/export), ZIP download, folder browser toggle |
| `frontend/app/(app)/documents/[id]/page.tsx` | Add: real preview pane (PDF.js/`<embed>` for PDF, `<img>` for images), duplicate-of banner if flagged |
| `frontend/components/documents/document-preview.tsx` (new) | Shared preview component used by both Documents and Poster Archive detail views |
| `frontend/app/(app)/dashboard/page.tsx` | New widgets: posters by status, storage usage, duplicates pending review, recent activity (real feed, not a static slice) |
| `frontend/app/(app)/activity/page.tsx` (new) | Dedicated activity/audit log page with filters |
| `frontend/components/layout/nav-items.ts`, `sidebar.tsx` | New "Activity" nav entry |
| `frontend/components/documents/folder-browser.tsx` (new) | Year → Month → District → Estate tree view, feeding the ZIP-export selection |
| `frontend/components/documents/bulk-toolbar.tsx` (new) | Shared selection-based action bar (approve/reject/status/delete/export) reused by Documents and Poster Archive |
| `frontend/components/documents/duplicate-banner.tsx` (new) | "This looks like a duplicate of X" inline warning + merge/dismiss actions |

## 6. Database Migrations Required

New Alembic revision(s), chained after `0005_poster_archive`:

1. **`0006_poster_status_and_folders`**
   - Add `Poster.status` (new `PosterStatus` enum: `draft`, `pending_review`,
     `approved`, `published`, `archived`, `rejected`) — additive column,
     backfilled from existing `approval_status` (`pending`→`pending_review`,
     `approved`→`approved`, `rejected`→`rejected`).
   - Decide: keep `approval_status` as-is for backward compat (safer) or
     drop it once `status` is proven — **recommend keeping both one release
     cycle**, deprecate `approval_status` later, to avoid a breaking change
     for anything still reading it.
   - Add `Poster.folder_path` (nullable `String`), `Document.folder_path`
     (nullable `String`) — computed and backfilled by a one-off script, not
     inline in the migration (keeps the migration itself fast/safe on a
     large table).
2. **`0007_duplicate_detection`**
   - Add `Document.content_hash`, `Poster.content_hash` (nullable, indexed).
   - New table `duplicate_matches` (`id`, `resource_type`, `resource_id`,
     `matched_resource_id`, `similarity_score`, `status` [pending/confirmed/
     dismissed], `created_at`).
3. **`0008_activity_feed_indexes`** (if needed)
   - Additional composite index on `AuditLog(resource_type, created_at)` for
     the new filterable activity feed — current single-column index on
     `created_at` only is fine for "recent 20" but not for filtered paging.

All three are additive/backward-compatible (new nullable columns, new
tables, new indexes) — **no destructive changes, no data loss risk**, and
each can ship independently if you want to phase the rollout.

## 7. API Changes Summary

| Endpoint | Change |
|---|---|
| `PATCH /api/posters/{id}` | Accept new `status` field (validated against `PosterStatus` transition rules, not a free-form set) |
| `POST /api/posters/bulk-status` (new) | Bulk status transition, mirrors existing `bulk-delete` |
| `POST /api/documents/bulk-action` (new) | Bulk approve/reject/delete for Documents (parity with Posters) |
| `POST /api/posters/export/zip` (new) | Streams a ZIP of selected/filtered posters' referenced files (only for posters that *have* a locally-stored attachment — pure Dropbox-link posters have nothing to zip, so this only applies once posters can carry attachments, see §8) |
| `GET /api/documents/export/zip` (new) | Streams a ZIP of selected/filtered documents preserving Year/Month/District/Estate structure |
| `GET /api/documents/duplicates`, `GET /api/posters/duplicates` (new) | List pending duplicate matches for review |
| `POST /api/documents/{id}/duplicates/{match_id}/resolve` (new) | Confirm/dismiss a duplicate match |
| `GET /api/activity` (new) | Paginated, filterable activity feed (replaces dashboard's inline `limit(20)`) |
| `GET /api/dashboard/stats` | Extended response: poster counts by status, storage usage bytes, pending-duplicates count |

## 8. Important Clarification Needed Before Phase 2

"One-click ZIP downloads that preserve folder structure" and "automatic
organization by Year → Month → District → Estate" both assume there are
**files on this server to organize**. Today, most `Poster` rows are just a
title + metadata + a link to a file living in *Dropbox*, not a file this
platform stores. Two paths forward, and I'd like your call before building
the ZIP/hierarchy feature:

- **(a)** Folder hierarchy + ZIP applies to `Document` (which already has
  real `source_path`/`output_path`/`archive_path` files on this server) now,
  and to `Poster` only once/if posters gain an actual uploaded-attachment
  field (`Poster.attachments` JSON column already exists, unused — this
  would start populating it).
- **(b)** Build a "fetch from Dropbox on demand" ZIP builder for posters
  too, which means adding Dropbox API integration (an external network
  dependency + auth token management this project doesn't have today) just
  to download the linked files into the ZIP.

**I recommend (a)**: ship hierarchy + ZIP for Documents in Phase 2, and add
poster attachment upload (small, additive) in Phase 4, so posters get the
same treatment once they have local files, without taking on a Dropbox API
integration as a dependency of this work. I'll proceed on that basis unless
you'd rather do (b).

## 9. Additional Enterprise Features Worth Considering

Beyond what you listed, these are the ones I'd actually recommend for a
government-office deployment, roughly in order of value:

1. **Full-text search backend (e.g. Postgres `tsvector` or SQLite FTS5)** —
   today "search" is `ILIKE '%...%'`, which is fine at hundreds of rows and
   will degrade (full table scans, no relevance ranking) once you're at the
   thousands-of-documents scale this plan targets.
2. **Retention/disposal policy automation** — government records often have
   mandated retention periods; an "archive after N years" / "flag for
   disposal review" scheduled job pairs naturally with the Year/Month
   hierarchy you're already asking for.
3. **Export/audit report generation** (PDF/Excel summary of activity for a
   given period) — `app/reporting/` already exists as an empty-ish stub
   directory; this is likely what it was meant for.
4. **Field-level audit diffing** — `AuditLog.detail` is a JSON blob today;
   storing structured before/after values for edits (not just "fields
   changed": [...]) makes "what did this record look like last Tuesday"
   answerable without reconstructing it from version files.
5. **Saved searches / smart folders** — lets staff bookmark "all Sha Tin
   posters pending review" as a one-click view.
6. **Rate-limited, audited public read-only share links** (optional, only if
   ever needed) — for handing a specific document to an outside party
   without giving them an account.

I would **not** recommend at this stage: real-time multi-user co-editing,
a plugin marketplace/SDK for external developers, or a mobile app — none of
those match "internal HK government office" scale/usage patterns and would
add substantial complexity for speculative benefit.

## 10. Implementation Phases (Ordered by Priority)

Each phase is independently shippable and testable; later phases assume
earlier ones are merged.

### Phase 1 — Status Workflow Overhaul
**Why first:** every other phase (bulk actions, dashboard, activity feed)
displays or acts on status; get the model right before building UI on it.
- Migration `0006` (`PosterStatus` + backfill).
- `app/api/schemas.py`, `app/api/routes/posters.py` status-transition
  endpoint with validated transitions (e.g. can't go `published`→`draft`
  directly).
- Frontend: `status-badge.tsx` extended, Poster Archive table/detail status
  control.
- **Complexity: Low. Risk: Low** (additive migration, backward-compatible
  field).

### Phase 2 — Folder Hierarchy + ZIP Export (Documents first, per §8)
- `app/storage/hierarchy.py`, `app/storage/archive_zip.py`.
- Migration `0006` also adds `folder_path` (can combine with Phase 1's
  migration into one revision if you'd rather not have two).
- Backfill script for existing rows' `folder_path`.
- `GET /api/documents/export/zip`.
- Frontend: `folder-browser.tsx`, ZIP-download button on Documents page.
- **Complexity: Medium. Risk: Medium** — streaming large ZIPs needs care
  (memory limits, timeouts on very large selections; needs a max-files/
  max-bytes guard per §4's config addition to prevent an accidental
  "export everything" DoS on the server).

### Phase 3 — Search Unification + Better Filtering
- `app/search/unified.py` consolidating Document/Poster filter logic.
- Extend filters (status, folder path).
- Frontend: Search page gains Poster results (currently Documents-only),
  Poster Archive filters gain status.
- **Complexity: Medium. Risk: Low** — pure refactor + additive filters, but
  touches two existing, working endpoints so needs solid regression tests
  before/after.

### Phase 4 — Duplicate Detection
- Migration `0007` (`content_hash`, `duplicate_matches` table).
- `app/dedup/duplicate_detector.py`: exact hash match at upload/import
  time; fuzzy match (title similarity for posters, perceptual hash for
  poster images) as an async/on-demand scan, not inline on every request.
- Poster attachment upload (small addition to `Poster` create/update flow,
  populating the existing unused `attachments` column) — needed so ZIP/
  dedup have real files to work with for posters too.
- Frontend: `duplicate-banner.tsx`, a "Review duplicates" queue page/section.
- **Complexity: Medium-High. Risk: Medium** — perceptual-image-hashing is
  the one genuinely new technical capability here (no existing code to
  build on); recommend a well-tested library (e.g. `imagehash`) rather than
  a custom implementation.

### Phase 5 — Bulk Actions Parity + Dashboard Overhaul
- `POST /api/documents/bulk-action`, `POST /api/posters/bulk-status`.
- `bulk-toolbar.tsx` shared component.
- Dashboard: poster-by-status widget, storage usage, duplicates-pending
  widget, real activity feed (backed by Phase 6's endpoint if sequenced
  after, or a temporary direct query otherwise).
- **Complexity: Low-Medium. Risk: Low.**

### Phase 6 — Activity Feed + Document Preview
- `GET /api/activity` with pagination/filters; migration `0008` composite
  index.
- `frontend/app/(app)/activity/page.tsx`.
- `document-preview.tsx` (PDF.js for PDF, native `<img>` for images, a
  "no preview available" fallback for everything else) used in both
  Documents detail and Poster Archive detail.
- **Complexity: Medium. Risk: Low** — PDF.js integration is the only new
  frontend dependency in this whole plan; needs a bundle-size check.

### Phase 7 — AI-Assisted Parsing Improvements
- Wire the *already-built* `RuleEngine` AI fallback for estates/districts
  into an actually-configured provider in at least one deployment profile
  (today it's wired but no provider is configured by default — see
  `app/api/deps.py`'s `get_rule_engine`), and extend AI use to title/
  poster-type disambiguation when regex/config both miss.
- **Complexity: Low (infra already exists). Risk: Low-Medium** — the risk
  is entirely about cost/latency/data-privacy of calling an external AI
  provider on office data; needs the org's sign-off on which provider (or
  confirm local-only per `app/ai/local_provider.py`) before enabling by
  default.

### Phase 8 — UI/UX Polish Pass
- Final visual pass across all touched pages once the functional work above
  is in place — this is intentionally last so polish isn't redone as
  underlying data/behavior shifts through Phases 1–7.
- **Complexity: Low. Risk: Low.**

---

## 11. Risks Worth Flagging Explicitly

1. **ZIP export as a DoS vector** — an unbounded "export everything" request
   against thousands of documents could exhaust server memory/disk or tie
   up a worker for minutes. Mitigation: hard cap on file count/total bytes
   per export (config-driven), streamed (not buffered-in-memory) ZIP
   writing, and rate-limiting matching the pattern already used elsewhere
   (`slowapi` limiter is already in place on other routes).
2. **Backfilling `folder_path`/`content_hash` on existing production rows**
   — needs a one-off script, tested against a copy of production data
   first, not run inline during a migration (migrations should stay fast
   and reversible; heavy computation belongs in a separate maintenance
   script per this project's existing convention, e.g. how
   `scripts/create_admin.py` and the backup scripts are already kept
   separate from `alembic/`).
3. **Perceptual image hashing is new, untested territory for this
   codebase** — needs its own test suite with real poster-image samples
   (false positives on near-identical-but-distinct posters would be worse
   than missing a few true duplicates, given these are official records).
4. **Two status fields coexisting (`approval_status` + `status`) during
   transition** — any code path that reads one but not the other risks
   showing stale/inconsistent state; needs an explicit, time-boxed
   deprecation plan for `approval_status`, not an indefinite dual-write.
5. **AI provider enablement (Phase 7) is a data-privacy decision, not just
   a technical one** — this is government office data; enabling a cloud AI
   provider by default without explicit sign-off would contradict this
   project's own existing "deterministic first, AI fallback only" policy
   documented in `app/rules/engine.py`.
6. **Search unification (Phase 3) touches two already-working, tested
   endpoints** — regression risk is entirely mitigated by keeping the
   existing test suites green throughout, not by the refactor being risky
   in itself; flagging so the review has that expectation set.

---

## 12. What I need from you before Phase 1 starts

1. Confirm the Option A vs B call in §2 (recommend A).
2. Confirm the ZIP/hierarchy scope call in §8 (recommend a: Documents now,
   Posters once they carry attachments).
3. Confirm which, if any, of the §9 "additional features" you want folded
   into this plan vs. treated as a separate future request.
4. Confirm the phase order in §10, or reprioritize (e.g. if bulk actions or
   dashboard matter more to daily staff usage than duplicate detection,
   that's a reasonable reordering).

Once confirmed, I'll start Phase 1 and report back before moving to Phase 2.
