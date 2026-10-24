# Task 07 — Learning Vertical Slice

## Status and scope

- Branch: `codex/task-07-learning-website`
- Base: `codex/task-04-data-engine` at `22da8b4`
- Implementation commit: `0d0e9d9`; report/branch update: `92cd3af`.
- Source books: six local PDFs were inventoried by metadata only. Their processing and redistribution rights are not established, so none was extracted or imported.
- Test source: generated one-page PDF fixture with synthetic Korean/Vietnamese content. It is not textbook data.

## Delivered flow

The private learning application now has:

- A Books page driven by the owner-scoped PostgreSQL/API records; no fixed list of six books.
- A per-book Lessons page with vocabulary/grammar counts, source pages, processing readiness, and learner progress.
- A lesson detail route with data-backed overview, vocabulary flashcards, grammar and personal notes, examples, dialogue, reading, listening metadata, and interactive exercises. Tabs only appear when the API returns corresponding approved content.
- Persistent operations for opening/completing a lesson, marking vocabulary learned, submitting exercises, and saving grammar notes.
- A signed, HttpOnly one-day web session gate. The password and API bearer token remain server-side; unauthenticated requests to private API proxy routes return 401. This remains a single-owner personal deployment, not multi-user account management.
- The exercise listing excludes answer keys. The answer is returned only from the submission endpoint when an approved key exists.

## Synthetic extraction and persisted records

The automated worker/API journey registered and processed the generated PDF,
reviewed source-backed records, queried them back through learner APIs, saved
learning state, then deleted the document and dependent data. The worker
persisted these records:

| Record | Count |
|---|---:|
| Lesson | 1 |
| Vocabulary entries | 2 |
| Word senses | 2 |
| Grammar patterns | 1 |
| Example sentences | 1 |
| Dialogue turns | 2 |
| Reading passages | 1 |
| Exercise records (group and question) | 2 |
| Exercise options | 2 |
| Sourced answer keys | 1 |
| Listening tracks | 1 |
| Transcripts | 1 |

The test verifies the records through the Books, Lessons, vocabulary,
flashcard, grammar-note, dialogue, exercise, progress, and quality-report API
routes. A correct multiple-choice response is shown only after submission.
Refresh-equivalent API reads confirm one learned vocabulary entry, one saved
exercise attempt, and one completed lesson. Separate regression coverage
verifies re-import idempotency, approved-record preservation, rollback/retry,
and deletion without orphaned learning or knowledge records.

The synthetic fixture's quality report explicitly does not estimate accuracy.
These counts and checks are pipeline evidence only—not evidence of textbook
coverage, correctness, or permission.

## Validation

- API suite: **27 passed** locally on SQLite.
- Learning journey test: passed with real PDF generation, extraction,
  provenance-aware review, API reads, progress writes, quality report, and
  deletion.
- Worker retry/re-import/delete test: passed.
- Alembic SQLite upgrade → downgrade to base → upgrade to head: passed.
- Web production build: passed.
- Web session/proxy tests: **3 passed**.
- Browser check: verified unauthenticated access is blocked, incorrect
  password is rejected, and the configured password opens the private UI. A
  production-mode Next.js app connected to an isolated FastAPI/SQLite database
  then completed the browser journey: book → lesson → Vietnamese flashcard →
  learned state → grammar note → multiple-choice submission → lesson complete
  → reload with progress retained.
- PostgreSQL 16 CI: migration upgrade → downgrade to base → upgrade to head
  passed; API/integration suite **26 passed, 1 skipped, 6 warnings**.
- PR CI run [40073698597](https://github.com/nhat965/HocTiengHanCung-T/actions/runs/40073698597)
  passed on branch commit `92cd3afd6a723847c26a980685bce9006424998a`.
  Both `api-postgres` and `web-build` passed; the latter includes the
  production dependency audit and frontend production build. Docker remains
  unavailable for a local PostgreSQL run.

## Remaining limitations

- No real textbook content was extracted or imported. Rights and content
  accuracy remain unverified.
- PostgreSQL 16 was validated in GitHub Actions only, not locally.
- The web login is one shared personal password, with one configured owner;
  there are no individual accounts or per-user sessions.
- Exercise formats beyond the currently extracted multiple-choice and
  free-text answer shapes need additional fixture coverage.
- The UI does not provide a human review editor; pending content remains
  available through the existing review API and is excluded from learner tabs.
