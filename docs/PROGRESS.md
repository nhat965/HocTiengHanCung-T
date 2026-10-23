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
- Structured JSON and quality report CLI output must remain beneath `PRIVATE_STORAGE_ROOT`. The standalone CLI is for inspection; the worker/API persistence integration was completed in Task 03.1 below.
- No structured extraction has been run against the six local textbooks.

### Task 01C — Quality Control & Review

- Added a quality report separating page coverage, structural counts, provenance presence, validation warnings, and human-review status.
- Transcript/track and answer/source linking are exercised with synthetic data; missing answers/transcripts are represented as missing rather than fabricated.
- Review metadata and APIs support pending/review-status filtering; a complete human review interface is not implemented.


## Task 03 — Private structured knowledge engine

- Added private source storage with per-owner hashed directories, SHA-256 verification, deletion, rights-status metadata, and ignored private-data paths.
- Rights default to `unverified`; API queueing and the worker both require a user-declared `authorized` status before raw extraction. The status is not independently verified.
- Protected private API routes with bearer-token authentication and owner scoping. This is a single-owner deployment boundary, not multi-user authentication.
- Added structured extractor modules, knowledge schema migration `20261023_0003`, internal persistence, quality reporting, and textbook/lesson knowledge query endpoints.
- Structured fixture acceptance output: 1 lesson, 2 vocabulary entries, 1 grammar pattern with 1 linked example sentence, 2 dialogue turns, 1 reading passage with 2 ordered paragraphs, an exercise group/question with 2 options and a sourced answer, and 1 listening track with a matched transcript. These are synthetic records, not book extraction results.
- Validation: API suite **10 passed**; Alembic downgrade to base and upgrade to head passed on temporary SQLite. PostgreSQL is unavailable in this environment, so PostgreSQL compatibility remains unverified.
- No PDF or extracted textbook content is included in this change.

## Task 03.1 — End-to-end worker and reliability hardening

- Connected the worker stages: rights check → raw PDF extraction and persistence → structured extraction → validation → structured persistence → persisted quality report.
- Import jobs expose the active/failing stage, attempts, record counts, and quality summary. Stale `extracting` jobs are recovered after 60 minutes on a subsequent worker invocation, subject to the retry limit.
- Structured persistence rolls back on mid-stage failure while retaining the committed raw layer for retry. Entity/provenance uniqueness constraints, idempotent upserts, and approved/reviewed-record preservation are covered by tests.
- Added generated-PDF integration coverage for Korean/Vietnamese vocabulary, grammar/example, reading, exercise/options/answer, listening/transcript, database persistence, API retrieval, re-import, rollback, and document deletion. Additional fixtures cover multi-column ordering, TOC/header filtering, rights enforcement, ownership, and stale-job recovery.
- Latest local validation: **16 API tests passed**; Alembic SQLite upgrade → downgrade → upgrade passed; `git diff --check` passed. Dependency deprecation warnings remain.
- Added PostgreSQL 16 CI service with Alembic round-trip and integration suite, plus dependency audits and frontend build. Docker is unavailable locally; PostgreSQL verification and CI result are **pending** until the workflow runs on the PR branch.
- CI dependency audits found and prompted updates to vulnerable Next.js/PostCSS and FastAPI/Starlette/pytest versions. The PostgreSQL round-trip exposed a lingering `importstate` enum on downgrade; the migration now drops it, with a SQLite round-trip recheck passing. PostgreSQL CI must rerun these fixes.
- The six textbook PDFs remain private, untracked, and unprocessed by this task. The generated-PDF test is not evidence of textbook extraction accuracy.

## Task 03.2 — PostgreSQL NUL and provenance hardening

- Root cause from PostgreSQL CI run `39996812765`: psycopg raised `DataError` for an `INSERT INTO source_pages ... raw_text ...` because PDF-extracted text contained U+0000. The parameter was `raw_text` (PostgreSQL `VARCHAR`/text); the fixture-generated PDF text survives PyMuPDF extraction with the NUL intact.
- Added a shared NUL-only sanitizer. Raw page/block/span/table extraction replaces U+0000 with U+FFFD, retains Korean/Vietnamese Unicode, and reports replacement counts in private quality metadata. SQLAlchemy String/Text/JSON bind types provide a final persistence guard, including nested JSON strings/keys.
- Removed provenance's first-span fallback. Only matching `raw_block` spans or exact table-row labels can resolve; unresolved references are skipped, counted, and produce a review-required warning without document text.
- Appendix headings now cap lesson segmentation before answer/transcript appendices; activity extraction still considers appendix blocks so sourced transcripts and answer keys can link to lesson content.
- Regression tests use a generated PDF containing actual NUL characters in page/block/span and table-cell text; the end-to-end test checks sanitized PostgreSQL-bound fields, private quality metadata, retry/rollback, API reads, idempotency, and deletion.
- Local validation: **19 API tests passed**; Alembic SQLite upgrade → downgrade → upgrade passed; frontend production build passed; `npm audit --omit=dev` reported **0 vulnerabilities**.
- Local Docker/PostgreSQL is unavailable. PostgreSQL 16 validation passed in GitHub Actions run `39999172404` on code commit `71e95eece2667110da691bfc20bfc6caa459e753`: Alembic upgrade/downgrade/upgrade, **18 passed, 1 skipped**, and the `web-build` job all succeeded; dependency audit reported no known vulnerabilities.

## Not yet verified

- PostgreSQL integration and migration behavior against a live server; CI is configured but has not yet reported a result.
- Full-book extraction, real textbook layout accuracy, human review, and accuracy metrics for any of the six books.
- OCR fallback: Tesseract is unavailable in this environment.
- AI, TTS, and STT provider integrations.

## 2026-10-24 — Task 04 data-engine vertical slice

- Audited PR #3, the raw/structured engines, migrations, worker, API, tests,
  quality reports, and six local untracked PDF files. The source books were not
  processed because reuse/processing rights have not been established.
- Added conservative NFC source normalization, PostgreSQL-safe control cleanup,
  stable track/source identifiers, and an extensible OCR contract whose safe
  default records unresolved content without guessing text.
- Separated sentence identity from source occurrence and added migration
  `20261024_0005`; ingestion reuses owner-scoped identities and deletion removes
  only identities that have become orphaned.
- Added owner-scoped review decisions/history, dialogue retrieval, approved-by-
  default JSON/JSONL/CSV dataset export, and document/lesson/type quality metrics.
- Local validation: **24 API tests passed**; SQLite Alembic
  upgrade → downgrade → upgrade passed. Both PostgreSQL 16 migration/test jobs,
  dependency audits, and both frontend builds passed on PR #4.
- The working dataset is a generated, authorized synthetic fixture: 1 lesson,
  2 vocabulary entries, 1 grammar pattern, 1 sentence/identity, 1 passage,
  2 exercise records, and 1 listening track with transcript. This is pipeline
  evidence, not evidence that any textbook corpus is complete or accurate.
