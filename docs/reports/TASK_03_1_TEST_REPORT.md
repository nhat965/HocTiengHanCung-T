# Task 03.1 — End-to-End Validation Report

## Scope

Validation covers the rights-aware PDF import worker, raw and structured
persistence, provenance, quality reporting, owner-protected API reads,
re-import behavior, rollback, and deletion. Tests use synthetic data, including
a PDF generated during the test run; no supplied textbook PDF or extracted
textbook data is included.

## Task 03.2 follow-up — PostgreSQL NUL and provenance

The failing PostgreSQL 16 job in workflow run
[39996812765](https://github.com/nhat965/HocTiengHanCung-T/actions/runs/39996812765)
reported `psycopg.DataError: PostgreSQL text fields cannot contain NUL
(0x00) bytes`. Redacted SQLAlchemy failure metadata identified:

```sql
INSERT INTO source_pages (
  source_document_id, pdf_page_number, printed_page_number, raw_text,
  korean_character_count, vietnamese_character_count, image_count,
  needs_ocr, extraction_method
) VALUES (...) RETURNING source_pages.id
```

The offending bound parameter was `raw_text`, written as a PostgreSQL text
value. The generated PDF fixture included U+0000, which PyMuPDF preserved in
extracted content. PostgreSQL rejects NUL in all text values; changing the
test assertion would only have hidden this earlier-stage failure.

Fixes include one shared NUL-only sanitizer, applied to extracted block, span,
table-cell, and page text; SQLAlchemy String/Text/JSON bind guards; and a
sanitization count in private extraction quality metadata. The raw PDF is
never changed. Regression coverage checks a generated PDF with actual NUL
characters in text and a table cell, NUL-free database page/block/span values,
JSON sanitization, Korean/Vietnamese preservation, and quality counts.

Provenance now requires an exact raw-block or table-row match. Unresolved
source references no longer attach to the first span on the page; persistence
counts them and emits a review-required warning containing page numbers only.
Appendix headings cap lesson end pages, while transcript and answer activity
records remain detectable from appendix pages.

## Local checks

| Check | Result |
| --- | --- |
| API test suite (FastAPI 0.161.1, Starlette 1.9.0, pytest 9.0.3) | **19 passed**, 97 dependency deprecation warnings |
| Generated-PDF worker → database → API integration | Passed as part of API suite |
| Re-import/idempotency and approved-record preservation | Passed |
| Structured-stage rollback on forced failure | Passed |
| Document deletion and orphan checks | Passed |
| Rights enforcement and owner-scoped access | Passed |
| Layout/TOC/header fixture checks | Passed |
| Stale-job recovery | Passed |
| Alembic SQLite upgrade → downgrade base → upgrade head | Passed |
| `git diff --check` | Passed |
| Frontend production build (Next.js 16.4.3, Turbopack) | Passed |
| Production dependency audit | Passed; 0 vulnerabilities reported |
| NUL PDF, exact provenance, and appendix regression tests | Passed |

Docker is not available in the local Windows environment, so a local
PostgreSQL service could not be started.

## PostgreSQL CI

The PR workflow configures PostgreSQL 16 and runs Alembic upgrade/downgrade/
upgrade, the API test suite against the migrated PostgreSQL database,
dependency audits, and the frontend production build. It must run successfully
on the pushed PR branch before PostgreSQL or CI acceptance can be claimed.
The initial run detected a vulnerable transitive PostCSS dependency under the
existing Next.js version. Next.js was upgraded to 16.4.3; the production audit
now reports zero vulnerabilities, and the local production build passes. The
Python audit also detected vulnerabilities in the pinned Starlette and pytest
versions; FastAPI, Starlette, and pytest were upgraded, and the API suite passed
against those versions locally. CI then exposed a PostgreSQL downgrade/upgrade
failure because the base migration left its enum type behind; the downgrade
now explicitly removes that PostgreSQL type. SQLite migration round-trip
passes with the fix.
**PostgreSQL 16 validation for the NUL/provenance changes is pending on the
updated PR branch; it is not yet claimed.**

## Known unverified behavior

- No accuracy or completeness claim for the six supplied textbooks or other
  real-world PDFs.
- OCR and image understanding are not implemented; image assets and all raw
  geometry are not fully mirrored in the structured database.
- `authorized` is a user declaration, not legal verification. Deployment
  authentication maps a bearer token to one configured owner and is not a
  multi-user identity system.
- Human review workflows and reviewer-based accuracy metrics are incomplete.
- PostgreSQL legacy-data compatibility, including unique-index migration in a
  populated database with duplicate records, still needs practical
  verification.
- No frontend unit tests are currently present; `npm run test:web` exits with
  "No test files found".
