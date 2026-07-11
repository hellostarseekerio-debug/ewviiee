# User Manual

## Signing in

Launch the desktop app (double-click the installed shortcut, or run
`python -m app.gui.main` from a terminal). You'll be asked for your
username and password. Ask your administrator for an account if you don't
have one — after 5 incorrect attempts your account locks for 15 minutes as
a security precaution.

The main window has a navigation list on the left: **Dashboard**, **Document
Explorer**, **Workflow Manager**, **Review**, **Search**, **Logs**,
**Settings**. What you can do on each screen depends on your role
(Viewer / Reviewer / Editor / Administrator) — buttons you don't have
permission for are simply disabled.

## Processing documents (Housing Estate Poster example)

Requires an Editor or Administrator account.

1. Open **Document Explorer**.
2. Drag and drop poster images and/or application PDFs onto the drop zone,
   or click **Browse…** to pick files. (Files must already be somewhere
   the system is configured to read from - ask your administrator if
   unsure, or use the upload option in the API if working remotely.)
3. Choose the workflow from the dropdown (e.g. "housing_estate_poster").
4. Click **Process Batch**. The progress bar tracks completion; each row in
   the table shows the detected district, estate, and result once done.
5. If a document fails validation (e.g. no estate could be identified), it
   is flagged with the exact reason rather than silently skipped — check
   the **Logs** screen for full detail.
6. Successfully processed documents move to the **Review** screen with
   status "pending" - they are not exported/archived as final until a
   Reviewer approves them.

## Reviewing and approving documents

Requires a Reviewer, Editor, or Administrator account.

Open **Review** to see every document awaiting a decision, with its AI and
OCR confidence scores. Select a row, optionally add notes, and click
**Approve** or **Reject**. Nothing is deleted on rejection - the document
stays available for re-processing or manual correction.

## Version history and rollback

Every time a document is generated, a new version is recorded (never
overwriting the previous one). If a mistake is found after the fact, an
Editor or Administrator can restore an earlier version via the API
(`POST /api/documents/{id}/rollback`) - this creates a new version pointing
at the old file rather than deleting anything.

## Searching documents

Open **Search** and fill in any combination of: estate, district, keyword,
politician, reference number, filename. Results appear in the table below;
click a row to preview details.

## Reviewing workflows

**Workflow Manager** lists every configured workflow (read from
`config/workflows/`) and shows its stage pipeline when selected. This
updates automatically as an administrator adds new workflows — no
application update needed.

## Changing appearance and privacy controls

**Settings** lets you switch between light and dark themes immediately, and
shows the currently configured AI provider. Administrators additionally see
a **Privacy** section with the cloud-AI switch — off by default, meaning no
document text ever leaves this machine. Turning it on is an office-wide
policy decision, not a per-document one; see `docs/PRIVACY.md`.

## Viewing and exporting logs

**Logs** shows recent application activity. Use **Export Logs…** to save a
combined application + audit log file for handover or troubleshooting.

## Getting help

If a document fails to process, the reason is always shown — never a
silent failure. Common reasons: OCR could not read the poster clearly
enough, or a required field (district, estate, politician, title) could not
be identified from the source document. Escalate to your system
administrator with the reason shown.
