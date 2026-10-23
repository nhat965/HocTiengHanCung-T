# Architecture

```
apps/web (Next.js) ──HTTPS/JSON──> apps/api (FastAPI) ──SQLAlchemy──> PostgreSQL
                                        │
                                        ├── PDF extraction adapter (PyMuPDF/OCR)
                                        ├── AI provider adapter
                                        └── Speech/TTS provider adapters
```

## Boundaries

- The web app never receives API keys or accesses source PDFs directly.
- The API accepts an import request only for server-visible files. It checks a SHA-256 checksum before creating a new source-document record.
- Extraction creates content only with source metadata. Uncertain extraction is `needs_review`.
- Deterministic exercise scoring happens without an LLM. Free-response evaluation goes through a provider adapter and records the evaluation context.

## PDF extraction status

PyMuPDF provides page text, blocks/spans and coordinates, font details, table
candidates, image assets, and PDF metadata. `app.extract_pdf` exports raw JSON
plus image assets; use `--pages START END` for a bounded extraction. The
volume-4 lesson-01 pilot is kept locally under the Git-ignored `data/`
directory.

The database worker currently persists page text, blocks, and provenance
spans. Table rows, individual span font/geometry data, and image assets are
available from the JSON exporter but are not yet persisted by the worker.
`Page.find_tables()` results remain candidates until reviewed. There is no OCR
provider installed; pages flagged by the OCR heuristic must be reviewed rather
than treated as OCR output.

## Local development

`DATABASE_URL` defaults to SQLite for tests and local exploration. Production must set a PostgreSQL URL and run Alembic migrations. The filesystem import root is controlled by `PDF_IMPORT_ROOT` to prevent arbitrary server file reads.
