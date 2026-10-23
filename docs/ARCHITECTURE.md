# Architecture

```
PDF in private import root
  -> validated, checksummed copy in owner-scoped private storage
  -> raw page/layout extraction (PyMuPDF)
  -> layout ordering and deterministic section/knowledge extractors
  -> validation and quality report
  -> private JSON output or internal persistence service
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
`app.extract_knowledge` transforms a raw JSON export into private structured
JSON and a quality report. These rules are tested against synthetic fixtures;
they have not been validated against the six local textbooks. The structured
CLI is not yet wired as an automatic PDF-worker stage, and production
structured-database ingestion is not yet exposed as an API operation.

Database migrations are mandatory; application startup does not create schema.
The latest migration has been exercised on SQLite. PostgreSQL migration
compatibility has not been verified against a live server.

## Local development

`DATABASE_URL` defaults to SQLite for tests and local exploration. Production
must set a PostgreSQL URL and run Alembic migrations. `PDF_IMPORT_ROOT`
restricts import paths, and `PRIVATE_STORAGE_ROOT` controls the private source
copy and structured JSON output locations.
