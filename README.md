# Korean Learning Platform

An evidence-first Korean learning platform for Vietnamese learners. It will import six *Tiếng Hàn Tổng Hợp* textbooks with page-level provenance, then build lessons, review, practice, TOPIK II preparation, and provider-backed AI support around verified material.

## Current status

Phase 1 foundation is being established. The repository deliberately contains no copied textbook PDFs or invented lesson data. See [the implementation plan](docs/IMPLEMENTATION_PLAN.md) and [progress](docs/PROGRESS.md).

## Structure

- `apps/web` — Next.js learner application.
- `apps/api` — FastAPI REST service and PDF import boundary.
- `docs` — architecture, API contract, implementation plan, and progress.

## Run locally

1. Install Node.js 20+ and Python 3.11+.
2. Copy `apps/api/.env.example` to `apps/api/.env` and choose a database URL. SQLite is acceptable locally; use PostgreSQL for shared/production environments.
3. Install API dependencies: `python -m pip install -r apps/api/requirements.txt`.
4. Run database migrations: `cd apps/api; python -m alembic upgrade head`.
5. Run API tests: `python -m pytest apps/api/tests`.
5. Install the web dependencies: `npm install`.
6. Run the API: `npm run dev:api`.
7. Run the web application in another terminal: `npm run dev:web`.

The import endpoint only permits PDFs beneath `PDF_IMPORT_ROOT`. Configure this to a dedicated local import directory; do not point it at a broad drive root in production. To extract, queue the registration using `POST /api/v1/imports/{id}/queue` and run `python -m app.worker --once` from `apps/api`.

### Importing the supplied textbooks

Create a dedicated folder such as `D:\korean-pdf-imports`, place or copy only approved PDFs there, then set `PDF_IMPORT_ROOT` to that folder. Register each file via `POST /api/v1/imports`. Registration validates the PDF and records its checksum/page count with state `registered`; it does not claim extraction has created lessons or vocabulary. Queue the job explicitly, then run the worker to create page-level raw extraction output.
