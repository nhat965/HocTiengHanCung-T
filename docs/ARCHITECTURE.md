# Architecture

```
PDF in private import root
  -> validated, checksummed copy in owner-scoped private storage
  -> raw page/layout extraction (PyMuPDF)
  -> layout ordering and deterministic section/knowledge extractors
  -> source-reference validation
  -> raw and structured database persistence with provenance
  -> persisted coverage/validation quality report
  -> authenticated, owner-scoped API reads
```

## Boundaries

- The web app never receives API keys or accesses source PDFs directly.
- Private API routes require a configured bearer token and are scoped to the configured `PRIVATE_OWNER_ID`. This is single-owner access control, not a multi-user identity system.
- The API accepts only server-visible files below `PDF_IMPORT_ROOT`, checks a SHA-256 checksum, and copies the source into a hashed owner directory under `PRIVATE_STORAGE_ROOT`.
- Rights status is recorded and defaults to `unverified`; raw API/worker extraction requires a user-declared `authorized` status. This is not legal verification, and private storage is not evidence of permission to process or redistribute a source.
- No PDF contents are sent to an AI or other external service. Logs should contain state/errors only, not extracted text.
- Source deletion removes the private PDF and its associated database records. There is no public PDF download endpoint.

## PDF extraction status

PyMuPDF extracts per-page text, blocks/spans and coordinates, font details,
table candidates, image assets, and PDF metadata. `app.extract_pdf` exports raw
JSON plus image assets. Table rows persisted by the worker are candidates, not
verified table structure. There is no OCR provider; pages flagged by the OCR
heuristic must be reviewed rather than treated as OCR output.

`app.services.knowledge` contains independent deterministic modules for layout,
lesson/section segmentation, vocabulary, grammar/examples, dialogues, reading,
exercises, listening tracks, transcripts, persistence, and quality reporting.
The worker runs these stages after raw extraction and stores per-stage progress,
failure stage, record counts, provenance, and quality summary on the import
job. A failure during structured persistence rolls back that stage while
leaving the successfully committed raw layer available for a retry. Re-running
a review-pending job is idempotent and preserves approved/reviewed records.
`app.extract_knowledge` remains a standalone private JSON inspection/export
command, not a database import path.

Synthetic fixture tests cover a generated PDF containing a Korean lesson title,
a Korean/Vietnamese table, grammar/example, reading paragraphs, exercise and
answer, and listening track/transcript, plus JSON fixtures for dialogue turns
and reading order. These checks do not establish accuracy on the six local
textbooks or any other real-world source.

Database migrations are mandatory; application startup does not create schema.
SQLite migration round-trips have been exercised locally. The CI workflow runs
the migration round-trip and persistence/API suite against a PostgreSQL service;
the latest CI result is required before claiming PostgreSQL validation.

Import jobs expose the current stage and failure stage in the authenticated API.
Jobs stuck in `extracting` for 60 minutes are requeued (within the retry limit)
or marked failed when the next worker invocation performs stale-job recovery.

## Local development

`DATABASE_URL` defaults to SQLite for tests and local exploration. Production
must set a PostgreSQL URL and run Alembic migrations. `PDF_IMPORT_ROOT`
restricts import paths, and `PRIVATE_STORAGE_ROOT` controls the private source
copy and structured JSON output locations.
