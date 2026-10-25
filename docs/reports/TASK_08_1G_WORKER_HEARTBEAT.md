# Task 08.1G — Worker Heartbeat

## Confirmed issue

`ImportJob.lease_expires_at` was refreshed only when the worker crossed a
processing-stage boundary. A single `extract_pages()` or `extract_knowledge()`
call longer than the 60-minute lease could therefore be recovered as stale
while the worker was still running. PR #7 already fenced writes with a worker
token and an unexpired lease, but it did not keep that lease alive during a
long blocking parse.

The heartbeat work is based on the tested Task 08.1E branch. PR #9 was audited
and contains only private web proxy validation/CI changes; it is not a
dependency of this worker fix.

## Root cause

The worker had no independent connection renewing the lease while PDF parsing
was in progress. Stage updates were the only lease refresh points. A stale
recovery transaction could consequently clear the token and requeue a healthy
worker before its next persistence boundary.

## Fix implementation

- Added a `LeaseHeartbeat` background thread using an independent
  `database.SessionLocal` connection.
- Renewal is an atomic `UPDATE` guarded by job id, `extracting` state, matching
  worker token and `lease_expires_at > now`; an expired lease is never revived.
- Heartbeat failures and ownership changes fail closed. The worker stops before
  the next stage or persistence transaction and never logs PDF content.
- Added heartbeat health checks before stage writes and every raw/structured
  persistence transaction. Existing `SELECT ... FOR UPDATE` ownership checks
  remain the final transaction fence against TOCTOU races.
- Heartbeat shutdown is joined in `finally` on completion, failure or lease
  loss. No schema or Alembic migration was required.

## Files changed

- `apps/api/app/services/extraction_worker.py`
- `apps/api/tests/test_extraction_worker.py`
- `docs/reports/TASK_08_1G_WORKER_HEARTBEAT.md`

## Regression tests

Added tests for:

1. Long-running extraction remaining leased while stale recovery runs.
2. Heartbeat shutdown after successful completion.
3. Heartbeat/database failure stopping the worker before raw persistence.
4. Existing PostgreSQL stale-worker recovery and stale-worker fencing.

The existing PostgreSQL tests also continue to cover atomic claiming,
overlapping page ranges, lease expiry and retry recovery.

## Test results

Local API tests were not available because this checkout has no Python runtime
or PostgreSQL service. GitHub Actions PostgreSQL 16 evidence passed:

- `40 passed, 1 skipped` in the API suite.
- Alembic `upgrade head`, `downgrade base`, `upgrade head` passed.
- Frontend dependency audit and production build passed.
- The skipped test is the existing non-PostgreSQL-specific conditional test;
  all heartbeat tests ran on PostgreSQL.

## Commit and CI

- Commits: `e75a36e` (heartbeat implementation), `6cacb2e` (regression test fix)
- Pull Request: [#10](https://github.com/nhat965/HocTiengHanCung-T/pull/10)
- GitHub Actions: [run 40112370893](https://github.com/nhat965/HocTiengHanCung-T/actions/runs/40112370893)

## Remaining risks

- A database outage during a heartbeat is handled fail-closed, but the job may
  remain `extracting` until stale recovery can reconnect and requeue it.
- A very long transaction that holds the import-job row lock can delay a
  heartbeat update; persistence still uses the transaction ownership fence and
  does not hold that lock while parsing the PDF.
- No OCR or PDF-content extraction behavior was changed in this task.
