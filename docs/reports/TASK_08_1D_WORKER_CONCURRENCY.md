# Task 08.1D — Concurrent Import Worker Safety

## Scope

This change hardens the database-backed PDF import worker for concurrent jobs,
overlapping page ranges, retries, and worker recovery. It does not include the
next exercise-parser task.

## Root cause

The worker previously selected queued jobs without an atomic claim and had no
worker ownership token or lease. A stale worker could therefore continue after
recovery and write later stages. Concurrent jobs for the same PDF also had no
source-document lock around raw-page and structured persistence, leaving unique
page and knowledge-record races to database constraint failures.

## Design and changes

- `ImportJob` now stores a random `worker_token` and `lease_expires_at`.
- Claims use PostgreSQL `SELECT ... FOR UPDATE SKIP LOCKED`, transition the job
  to `extracting`, and commit the claim before PDF parsing.
- Every stage heartbeat and write validates the token and an unexpired lease.
  Recovery clears the lease, so an old worker cannot commit after requeue.
- Raw and structured persistence lock the `SourceDocument` row while the
  transaction is open. Existing `SourcePage` and knowledge rows are reused,
  keeping overlapping ranges idempotent.
- Deleting a source document while any job is extracting returns HTTP 409.

## Files changed

- `apps/api/app/models.py`
- `apps/api/app/services/extraction_worker.py`
- `apps/api/app/routers/imports.py`
- `apps/api/migrations/versions/20261024_0010_import_worker_leases.py`
- `apps/api/tests/test_extraction_worker.py`
- `apps/api/tests/test_imports.py`

## Regression coverage

- Two PostgreSQL workers racing for one queued job: one claim and one attempt.
- Two workers processing overlapping ranges: no duplicate source pages.
- An expired worker lease recovered while parsing: the stale worker cannot
  commit and the retry succeeds.
- Existing retry/idempotency and approved-content preservation tests.
- Deletion is blocked while a worker owns an extracting job.

## Verification

Local API tests could not run because this checkout does not have Python or
PostgreSQL tooling installed. The authoritative evidence is the PostgreSQL
GitHub Actions job for the pull request. Frontend tests/build are unchanged by
this backend-only task.

- Implementation commit: `1b7fe004b9d434a5441513f1998a1c45eba0038f`
- GitHub Actions: [run 40101629505](https://github.com/nhat965/HocTiengHanCung-T/actions/runs/40101629505)
- Pull request: [#7](https://github.com/nhat965/HocTiengHanCung-T/pull/7)

## Remaining risks

The lease is refreshed at stage boundaries; a single PDF parsing call longer
than the lease duration would require a heartbeat extension in the parser
itself. PostgreSQL CI is required to validate row-lock behavior; SQLite is not
used as concurrency evidence.
