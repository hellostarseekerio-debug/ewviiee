# User Manual

## Starting the application

Launch the desktop app (double-click the installed shortcut, or run
`python -m app.gui.main` from a terminal). The main window has a navigation
list on the left: **Dashboard**, **Document Explorer**, **Workflow
Manager**, **Search**, **Logs**, **Settings**.

## Processing documents (Housing Estate Poster example)

1. Open **Document Explorer**.
2. Drag and drop poster images and/or application PDFs onto the drop zone,
   or click **Browse…** to pick files.
3. Click **Process Batch**. The progress bar tracks completion; each row in
   the table shows the detected district, estate and confidence once done.
4. If a document fails validation (e.g. no estate could be identified), it
   is flagged rather than silently skipped — check the **Logs** screen for
   the reason.
5. Finished documents are exported to the configured export folder and
   archived automatically.

## Searching documents

Open **Search** and fill in any combination of: estate, district, keyword,
politician, reference number, filename. Results appear in the table below;
click a row to preview details.

## Reviewing workflows

**Workflow Manager** lists every configured workflow (read from
`config/workflows/`) and shows its stage pipeline when selected. This
updates automatically as an administrator adds new workflows — no
application update needed.

## Changing appearance

**Settings** lets you switch between light and dark themes immediately, and
shows the currently configured AI provider (change it in `.env` to persist
across restarts).

## Viewing and exporting logs

**Logs** shows recent application activity. Use **Export Logs…** to save a
combined application + audit log file for handover or troubleshooting.

## Getting help

If a document fails to process, the reason is always shown — never a
silent failure. Common reasons: OCR could not read the poster clearly
enough, or a required field (district, estate, politician, title) could not
be identified from the source document. Escalate to your system
administrator with the reason shown.
