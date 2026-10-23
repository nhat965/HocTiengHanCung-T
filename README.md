# Korean Learning Platform

An evidence-first Korean learning platform for Vietnamese learners. It will import six *Tiếng Hàn Tổng Hợp* textbooks with page-level provenance, then build lessons, review, practice, TOPIK II preparation, and provider-backed AI support around verified material.

## Current status

The API, raw PDF extraction foundation, and a reusable structured-knowledge
pipeline are implemented. The structured pipeline is verified with synthetic
fixtures only. The six source PDFs remain local and untracked; this task has not
extracted their contents into structured records. PostgreSQL migration testing
is still outstanding. See the [source audit](docs/reports/SOURCE_PDF_AUDIT.md),
[raw pilot results](docs/reports/EXTRACTION_RESULTS.md),
[Task 03 report](docs/reports/LESSON_01_STRUCTURED_EXTRACTION.md),
[data quality report](docs/reports/DATA_QUALITY.md), and [progress](docs/PROGRESS.md).

PDFs and all extracted text/images/JSON are private data. Keep imports and
outputs under ignored private storage directories; never commit them unless
distribution rights have been confirmed.

## Structure

- `apps/web` — Next.js learner application.
- `apps/api` — FastAPI REST service and PDF import boundary.
- `docs` — architecture, API contract, implementation plan, and progress.

## Run locally

1. Install Node.js 20+ and Python 3.11+.
2. Copy `apps/api/.env.example` to `apps/api/.env`. Set a strong `PRIVATE_API_TOKEN`, a deployment-specific `PRIVATE_OWNER_ID`, private storage/import directories, and a database URL. SQLite is for local development; use PostgreSQL for shared/production environments.
3. Install API dependencies: `python -m pip install -r apps/api/requirements.txt`.
4. Run database migrations: `cd apps/api; python -m alembic upgrade head`.
5. Run API tests: `python -m pytest apps/api/tests`.
5. Install the web dependencies: `npm install`.
6. Run the API: `npm run dev:api`.
7. Run the web application in another terminal: `npm run dev:web`.

Private API routes require `Authorization: Bearer <PRIVATE_API_TOKEN>`. This is a single-owner deployment boundary, not multi-user account management. The import endpoint only permits PDFs beneath `PDF_IMPORT_ROOT` and copies the PDF into owner-scoped `PRIVATE_STORAGE_ROOT`. Configure a dedicated import directory; do not point it at a broad drive root in production. Rights default to `unverified`; extraction queueing requires `rights_status: "authorized"`. That value is a user declaration, not an independent rights verification, and private storage does not establish permission to process or redistribute content.

To extract raw pages, queue registration using `POST /api/v1/imports/{id}/queue` and run `python -m app.worker --once` from `apps/api`.

To export a bounded page range as directly inspectable JSON and image files, choose a private output path (the example output is ignored by Git):

```powershell
cd apps/api
python -m app.extract_pdf "D:\approved-imports\volume-4.pdf" --pages 18 35 --output "private-data\raw\book-4\lesson-01-raw.json"
```

Run the structured CLI on a private raw JSON export:

```powershell
cd apps/api
python -m app.extract_knowledge "private-data\raw\book-4\lesson-01-raw.json" --output "private-data\structured\book-4\lesson-01.json"
```

The CLI writes structured JSON and a separate quality JSON report. These tools
do not claim source accuracy and do not extract the six supplied textbooks in
this task. Structured database writes are currently exercised through the
internal persistence service and fixtures; they are not yet an automated stage
of the PDF worker.

### Importing the supplied textbooks

Create a dedicated folder such as `D:\korean-pdf-imports`, place or copy only approved PDFs there, then set `PDF_IMPORT_ROOT` to that folder. Register each file via `POST /api/v1/imports`. Registration validates the PDF and records its checksum/page count with state `registered`; it does not claim extraction has created lessons or vocabulary. Queue the job explicitly, then run the worker to create page-level raw extraction output.
