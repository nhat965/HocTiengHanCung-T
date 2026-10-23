# Implementation plan

## Repository assessment — 2026-10-23

The GitHub remote `nhat965/HocTiengHanCung-T` and its attached local checkout were empty at assessment time. There was no existing application, dependency manifest, database schema, PDF copy, or prior implementation to preserve.

Six source PDFs are available outside the repository at user-provided `D:\` paths. Their sizes range from approximately 19 MB to 120 MB. Phase 1 records and supports their import without copying copyrighted source files into Git or fabricating content from them. Text/OCR quality must be measured during an actual import.

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

Build PyMuPDF/OCR extraction, table-of-contents/lesson segmentation, review queue, sourced vocabulary and grammar persistence, and administrator import review. Add fixtures using rights-cleared PDFs only.

Task 01 adds the raw page/block/span layer, an explicit extraction queue/worker, preliminary profile-driven segmentation, knowledge-base schema, and quality-report foundation. The structured extractors and the volume-4 pilot remain blocked on a runnable Python environment and must not be represented as complete.

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

- PDF extraction quality, OCR language packs, and exact lesson boundaries cannot be certified until the importer is run on the supplied PDFs.
- The selected authentication provider, AI provider, TTS/STT provider, and deployment target remain configuration decisions.
- The official TOPIK II blueprint is intentionally deferred until Phase 4 research.
