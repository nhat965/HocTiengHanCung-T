# Private document and knowledge API

Base URL: `http://localhost:8000/api/v1`

All document and knowledge routes require bearer authentication. The API server
maps the configured secret to one `PRIVATE_OWNER_ID`; this is not multi-user
account management. Never expose the server secret in the public frontend. No
route downloads source PDFs.

| Method | Path | Purpose |
| --- | --- | --- |
| `GET` | `/health` | Liveness and database availability check. |
| `GET` | `/textbooks` | List the configured owner's textbooks. |
| `POST` | `/imports` | Register an allowed PDF, copy it to private storage, and record rights status. |
| `POST` | `/imports/{job_id}/queue` | Queue a registered/retryable job or explicitly re-run a review-pending job. |
| `GET` | `/imports/{job_id}` | Retrieve owner-scoped job state, current stage, failure stage, attempts, and record counts. |
| `GET` | `/imports/{job_id}/report` | Return the persisted structured quality summary and raw extraction coverage. |
| `DELETE` | `/imports/documents/{document_id}` | Delete the source and its associated records when no other source shares the textbook. |
| `GET` | `/textbooks/{id}/lessons` | Return source-derived lesson boundaries. |
| `GET` | `/lessons/{id}` | Return one owner-scoped lesson. |
| `GET` | `/lessons/{id}/vocabulary` | Return vocabulary, meanings, source page, and review status. |
| `GET` | `/lessons/{id}/grammar` | Return grammar patterns, source page, and review status. |
| `GET` | `/lessons/{id}/exercises` | Return exercises, options, available answers, and source page. |
| `GET` | `/lessons/{id}/sentences` | Return source-backed sentences. |
| `GET` | `/lessons/{id}/reading` | Return reading passages. |
| `GET` | `/lessons/{id}/listening` | Return track identifiers and transcript availability; no fabricated audio. |

`POST /imports` request:

```json
{
  "source_path": "C:/approved-imports/textbook-1.pdf",
  "title": "Synthetic authorized document",
  "level": "beginner",
  "volume_number": 1,
  "rights_status": "authorized"
}
```

`rights_status` may be `unverified` (the default), `authorized`, or
`restricted`. Queueing and worker extraction both require `authorized`; this is
a user-supplied declaration, not legal verification or proof of permission.

The import worker reports the current `stage`: `rights_check`,
`raw_extraction`, `raw_persistence`, `structured_extraction`, `validation`,
`structured_persistence`, `quality_report`, or `complete`. On failure the job
state is `failed`, `stage` is `failed`, and `failure_stage` identifies where it
stopped. Errors are logged without extracted document text. Stale `extracting`
jobs are recovered on the next worker invocation after 60 minutes, subject to
the retry limit.

Successful processing ends in `needs_review`. Raw and structured data,
provenance, record counts, and a coverage/validation summary are persisted
before this state is set. It does not indicate source accuracy or human
approval. Re-queueing a `needs_review` job re-runs idempotent persistence and
does not overwrite records whose review status is `approved` or `reviewed`.

List endpoints for vocabulary, grammar, exercises, sentences, reading, and
listening accept `offset`, `limit` (1–100), and `review_status` query
parameters. `GET /health` is the only unauthenticated endpoint.

The standalone structured JSON CLI is an offline inspection/export tool. The
rights-aware API worker is the integrated database persistence workflow.
