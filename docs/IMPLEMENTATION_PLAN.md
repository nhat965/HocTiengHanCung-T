# Implementation plan

## Repository assessment — 2026-10-23

At initial assessment the remote `nhat965/HocTiengHanCung-T` had one scaffold commit and no PDF files. The current workspace contains six user-provided PDFs under `docs/`, but Git reports them as untracked; their presence on GitHub is not verified and they are not included in commits.

The six local PDFs have been audited for file size, SHA-256, metadata, page count, text availability, language character counts, images, and candidate tables. The measured audit is in `docs/reports/SOURCE_PDF_AUDIT.md`. Text extraction has only been run on a bounded volume-4 lesson-01 range; the source files and extracted textbook content remain uncommitted.

## Chosen architecture

| Area | Decision | Reason |
| --- | --- | --- |
| Web | Next.js App Router + TypeScript + Tailwind CSS | Responsive learner UI with typed API boundary. |
| API | FastAPI + Pydantic + SQLAlchemy | Typed REST contracts and dependable import/job workflows. |
| Database | PostgreSQL in production, SQLite for local tests | Production relational integrity with low-friction development. |
| Migrations | Alembic | Reviewable schema evolution. |
| PDF | PyMuPDF first; OCR adapter only for pages with insufficient extractable text | Avoids invented textbook content and keeps uncertain pages reviewable. |
| AI/audio | Provider interfaces configured entirely on the server | Allows model/provider changes without exposing credentials. |

## Phase plan

### Phase 1 — Foundation (in progress)

1. Create monorepo layout, environment examples, and local orchestration.
2. Add FastAPI service, health endpoint, database boundary, and initial migration.
3. Add a real, idempotent PDF-import job endpoint that stores the checksum and begins extraction asynchronously.
4. Add a Next.js learner shell with usable loading/error states and API-health status.
5. Document setup, architecture, API, and current limitations.

**Acceptance criteria:** API starts with a configured database; duplicate PDF bytes return the existing import; no textbook lesson/vocabulary data is invented; the web app has a real API health check; automated tests cover the import idempotency boundary.

### Phase 2 — Textbook engine

1. Complete durable raw database persistence for spans, tables, images, and page metadata.
2. Improve layout-aware segmentation and identify real lesson starts independently of table-of-contents entries.
3. Add OCR provider support or keep affected regions explicitly flagged for human review.
4. Build sourced vocabulary, grammar, sentence, dialogue, reading, exercise, transcript, and answer-key extractors.
5. Add quality metrics and review tools; do not assign high confidence solely because PDF text is extractable.

**Current measured progress:** raw JSON and image export works on a synthetic fixture and a bounded real volume-4 lesson-01 range. The source audit covers all six local PDFs. No structured book data has been extracted, no OCR has run, and a full-book import has not been verified. See `docs/reports/EXTRACTION_RESULTS.md`.

### Phase 3 — Learning engine

Build sourced lesson pages, deterministic exercises, progress, mistake history, and a testable spaced-repetition scheduler.

### Phase 4 — TOPIK engine

Research official TOPIK II formats before recording the versioned question-type blueprint. Then implement question bank, sessions, scoring, timing, and review. No copyrighted exam copy is stored as generated content.

### Phase 5 — AI engine

Add server-side provider abstractions, JSON-schema validation, independent validation/review gates, quotas, and source-aware tutor responses.

### Phase 6 — Listening and speaking

Add cached TTS, transcript gating, STT provider adapter, and pronunciation feedback whose limits are explicit.

### Phase 7 — QA and deployment

Add Playwright, security review, backups, observability, CI, and deployment playbooks.

## Data model direction

The first migration establishes `textbooks`, `source_documents`, `import_jobs`, `lessons`, `vocabulary`, `grammar_points`, and `learning_progress`. Later migrations introduce review history, exercise attempts, audio assets, TOPIK templates/questions/attempts, AI jobs, and authentication identities. Every textbook-derived record carries an explicit provenance path; generated records carry generation metadata and status.

## Risks and decisions deferred

- Tesseract is not installed; OCR language packs and OCR-based extraction are not available in this environment.
- Table detection is structural and may mistake decorative lines or exercise layouts for data tables.
- The current API worker does not yet persist every JSON raw artifact (table rows, span font/geometry, image assets).
- Full-book and structured extraction accuracy has not been established; human review remains necessary.
- The selected authentication provider, AI provider, TTS/STT provider, and deployment target remain configuration decisions.
- The official TOPIK II blueprint is intentionally deferred until Phase 4 research.
