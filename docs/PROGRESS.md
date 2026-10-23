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

- Reusable deterministic extractors now cover lesson/section segmentation, table-based Korean–Vietnamese vocabulary, grammar/examples, dialogue turns, reading paragraphs, exercises/options/answers, listening track identifiers, and transcripts.
- Added provenance, extraction version, review status, idempotent persistence, and protected knowledge read endpoints.
- Synthetic fixture verifies records and source-page links across two pages, including vocabulary, grammar/example, dialogue, reading, question/options/answer, and track/transcript matching.
- TOC-page and running-header false positives are covered by a separate fixture test. Source-page provenance refuses ambiguous matches when multiple source PDFs share page numbers unless a source document ID is specified.
- Structured JSON and quality report CLI output must remain beneath `PRIVATE_STORAGE_ROOT`. The CLI is not yet integrated with an automatic PDF worker/API database-ingestion step.
- No structured extraction has been run against the six local textbooks.

### Task 01C — Quality Control & Review

- Added a quality report separating page coverage, structural counts, provenance presence, validation warnings, and human-review status.
- Transcript/track and answer/source linking are exercised with synthetic data; missing answers/transcripts are represented as missing rather than fabricated.
- Review metadata and APIs support pending/review-status filtering; a complete human review interface is not implemented.


## Not yet verified

- Structured database ingestion through a production API/worker path.
- Full-book extraction or structured knowledge extraction for any of the six books.
- OCR fallback: Tesseract is unavailable in this environment.
- PostgreSQL migrations against a live database. Alembic upgrade/downgrade/upgrade was verified on temporary SQLite only.
- AI, authentication, TTS, and STT provider integrations.

## Task 03 — Private structured knowledge engine

- Added private source storage with per-owner hashed directories, SHA-256 verification, deletion, rights-status metadata, and ignored private-data paths.
- Rights default to `unverified`; API queueing and the worker both require a user-declared `authorized` status before raw extraction. The status is not independently verified.
- Protected private API routes with bearer-token authentication and owner scoping. This is a single-owner deployment boundary, not multi-user authentication.
- Added structured extractor modules, knowledge schema migration `20261023_0003`, internal persistence, quality reporting, and textbook/lesson knowledge query endpoints.
- Structured fixture acceptance output: 1 lesson, 2 vocabulary entries, 1 grammar pattern with 1 linked example sentence, 2 dialogue turns, 1 reading passage with 2 ordered paragraphs, an exercise group/question with 2 options and a sourced answer, and 1 listening track with a matched transcript. These are synthetic records, not book extraction results.
- Validation: API suite **10 passed**; Alembic downgrade to base and upgrade to head passed on temporary SQLite. PostgreSQL is unavailable in this environment, so PostgreSQL compatibility remains unverified.
- No PDF or extracted textbook content is included in this change.
