# Korean Learning Platform

An evidence-first Korean learning platform for Vietnamese learners. It imports
documents privately and builds lessons, review, practice, TOPIK II preparation,
and provider-backed AI support around reviewed material.

## Current status

The API supports an end-to-end private import worker: raw extraction,
structured extraction, validation, database persistence, and per-job quality
reporting. The workflow is tested with a generated synthetic PDF only. The six
source PDFs remain local and untracked; this task has not extracted their
contents into structured records. PostgreSQL validation is configured in CI
but is pending a successful CI run. See the [source audit](docs/reports/SOURCE_PDF_AUDIT.md),
[raw pilot results](docs/reports/EXTRACTION_RESULTS.md),
[Task 03 report](docs/reports/LESSON_01_STRUCTURED_EXTRACTION.md),
[data quality report](docs/reports/DATA_QUALITY.md),
[Task 03.1 test report](docs/reports/TASK_03_1_TEST_REPORT.md), and
[progress](docs/PROGRESS.md).

PDFs and all extracted text/images/JSON are private data. Keep imports and
outputs under ignored private storage directories; do not commit them unless
distribution rights have been confirmed.

## Structure

- `apps/web` — Next.js learner application.
- `apps/api` — FastAPI REST service, private PDF import and extraction worker.
- `docs` — architecture, API contract, implementation plan, and progress.

## Run locally

1. Install Node.js 20+ and Python 3.11+.
2. Copy `apps/api/.env.example` to `apps/api/.env`. Set a strong API bearer
   secret, a deployment-specific owner ID, private storage/import directories,
   and a database URL. SQLite is for local development; use PostgreSQL for
   shared/production environments.
3. Install API dependencies: `python -m pip install -r apps/api/requirements.txt`.
4. Run database migrations from `apps/api`: `python -m alembic upgrade head`.
5. Run API tests: `python -m pytest apps/api/tests`.
6. Install web dependencies: `npm install`.
7. Run the API: `npm run dev:api`.
8. Run the web application in another terminal: `npm run dev:web`.

Private API routes require bearer authentication and are scoped to the
configured owner. Do not place the API bearer secret in the public frontend.
This is a single-owner deployment boundary, not multi-user account management.
Imports must be below `PDF_IMPORT_ROOT` and are copied into owner-scoped
`PRIVATE_STORAGE_ROOT`. Rights default to `unverified`; queueing extraction
requires a user-declared `authorized` status. This declaration is not legal
verification, and private storage does not establish permission to process or
redistribute content.

After registration and a rights declaration, queue the import through
`POST /api/v1/imports/{job_id}/queue` and run `python -m app.worker --once`
from `apps/api`. The worker performs raw and structured extraction, persists
records and provenance, and saves stage, counts, and a quality summary.
`GET /api/v1/imports/{job_id}` reports progress; the `/report` subroute returns
the quality report. Successful processing ends in `needs_review`, not an
accuracy-approved state. Stale extracting jobs are recovered on the next
worker invocation after the timeout.

To export a bounded page range as directly inspectable JSON and image files,
choose an output path beneath private storage:

```powershell
cd apps/api
python -m app.extract_pdf "D:\approved-imports\volume-4.pdf" --pages 18 35 --output "private-data\raw\book-4\lesson-01-raw.json"
```

The standalone structured JSON CLI writes inspectable JSON and a quality
report; the worker is the database persistence workflow:

```powershell
cd apps/api
python -m app.extract_knowledge "private-data\raw\book-4\lesson-01-raw.json" --output "private-data\structured\book-4\lesson-01.json"
```

Neither the CLI nor worker claims source accuracy. No supplied textbook was
extracted in this task.

### PostgreSQL development and tests

From `apps/api`, run `docker compose up -d postgres`, set `DATABASE_URL` and
`TEST_DATABASE_URL` to the PostgreSQL URL in `.env.example`, then run
`python -m alembic upgrade head`, `python -m alembic downgrade base`,
`python -m alembic upgrade head`, and `python -m pytest tests -q`. Do not use
`docker compose down -v` unless you intend to delete the local database volume.

### Importing documents

Create a dedicated folder such as `D:\korean-pdf-imports`, place only documents
you are permitted to process there, and set `PDF_IMPORT_ROOT` to that folder.
Register, declare rights status, queue, then run the worker. `registered` means
no extraction has run; `needs_review` means raw and structured records were
persisted but still need human review.
