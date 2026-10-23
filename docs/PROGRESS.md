# Progress

## 2026-10-23 — Phase 1 started

- Repository assessed: empty local checkout and empty GitHub remote.
- Source PDFs identified at user-provided local paths; no content was fabricated or committed.
- Planning and architecture documents added.
- Foundation scaffold implemented:
  - FastAPI application with health, textbook listing, and a restricted-path, SHA-256-idempotent PDF registration endpoint.
  - Initial Alembic migration for textbook documents and import jobs.
  - Next.js dashboard with a live API health check, explicit unavailable state, keyboard-focus styling, and responsive navigation.
  - Web production build completed successfully.
- Responsive verification completed at 320, 375, 414, and 768 px: the document width equalled the viewport width at each breakpoint.
- UI detector completed for `apps/web/app` with no findings.

## 2026-10-23 — Task 01 PDF Data Engine foundation

- Verified metadata for the supplied volume-4 PDF: readable, unencrypted, 338 pages.
- Added explicit registration, queue, extraction, failure/retry, and extracted states.
- Added page/block/span persistence, configurable boundary detection, PDF validation, a standalone worker, knowledge-base schema migration, quality report endpoint, and source-backed lesson APIs.
- Added Docker Compose for local PostgreSQL and integration tests for valid/corrupt PDFs.

### Task 01A — Raw PDF Extraction

- Implemented per-page text, block/span coordinates, page dimensions and rotation, table rows, extracted image assets with placement metadata, source PDF metadata, and SHA-256.
- Added a standalone JSON export command; JSON references extracted images in a neighboring assets folder.
- API tests ran with the bundled Python 3.11 runtime: **4 passed** using a synthetic PDF fixture.
- A bounded real-source pilot was run for volume 4, lesson 01: PDF pages 18–35 (printed pages 17–34), 18 pages, 419 blocks, 3,735 spans, 14 detected table candidates, and 54 images. JSON and images are local and Git-ignored.
- A six-file source audit was performed. All PDFs are present locally but untracked; audit measurements are in `docs/reports/SOURCE_PDF_AUDIT.md`.
- The pilot has not undergone visual table/layout verification and contains no structured knowledge records.
- Added an inclusive page-range option to the JSON export CLI.
- Fixed extraction-worker re-runs to upsert source pages/blocks and avoid deleting lessons or reviewed spans. Raw extraction spans no longer receive confidence `1.0` merely because text was read.
- API tests: **5 passed**, including a re-import test that checks idempotency and preservation of reviewed records. Alembic upgrade passed on temporary SQLite.

### Task 01B — Structured Knowledge Extraction

- Pending: lesson/section parsing and source-backed vocabulary, grammar, examples, dialogues, passages, and question relationships.

### Task 01C — Quality Control & Review

- Pending: transcript/answer-key matching, completeness checks against PDF pages, and human review tooling.


## Not yet verified

- Full-book extraction or structured knowledge extraction for any of the six books.
- OCR fallback: Tesseract is unavailable in this environment.
- PostgreSQL migrations against a live database.
- AI, authentication, TTS, and STT provider integrations.
