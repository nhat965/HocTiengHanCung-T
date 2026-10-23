# Task 03.1 — End-to-End Validation Report

## Scope

Validation covers the rights-aware PDF import worker, raw and structured
persistence, provenance, quality reporting, owner-protected API reads,
re-import behavior, rollback, and deletion. Tests use synthetic data, including
a PDF generated during the test run; no supplied textbook PDF or extracted
textbook data is included.

## Local checks

| Check | Result |
| --- | --- |
| API test suite | **16 passed**, 6 dependency deprecation warnings |
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

Docker is not available in the local Windows environment, so a local
PostgreSQL service could not be started.

## PostgreSQL CI

The PR workflow configures PostgreSQL 16 and runs Alembic upgrade/downgrade/
upgrade, the API test suite against the migrated PostgreSQL database,
dependency audits, and the frontend production build. It must run successfully
on the pushed PR branch before PostgreSQL or CI acceptance can be claimed.
The initial run detected a vulnerable transitive PostCSS dependency under the
existing Next.js version. Next.js was upgraded to 16.4.3; the production audit
now reports zero vulnerabilities, and the local production build passes.
**The workflow rerun for that fix is pending; PostgreSQL validation is not yet
claimed.**

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
