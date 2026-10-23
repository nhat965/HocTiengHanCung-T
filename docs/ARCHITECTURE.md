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

## Local development

`DATABASE_URL` defaults to SQLite for tests and local exploration. Production must set a PostgreSQL URL and run Alembic migrations. The filesystem import root is controlled by `PDF_IMPORT_ROOT` to prevent arbitrary server file reads.
