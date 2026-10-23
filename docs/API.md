# API (Private document and knowledge API)

Base URL: `http://localhost:8000/api/v1`

All document and knowledge routes require `Authorization: Bearer <PRIVATE_API_TOKEN>`.
The token maps to the configured `PRIVATE_OWNER_ID`; it does not implement
per-user accounts or per-document grants. No route downloads source PDFs.

| Method | Path | Purpose |
| --- | --- | --- |
| `GET` | `/health` | Liveness and database availability check. |
| `GET` | `/textbooks` | List the configured owner's textbooks. |
| `POST` | `/imports` | Register an allowed PDF; copy to private storage and record rights status. |
| `POST` | `/imports/{id}/queue` | Queue a registered/retryable raw extraction job. |
| `GET` | `/imports/{id}` | Retrieve owner-scoped import-job state. |
| `GET` | `/imports/{id}/report` | Return raw page coverage and extraction quality metrics. |
| `DELETE` | `/imports/documents/{id}` | Remove a source and its associated records, when no other source shares the textbook. |
| `GET` | `/textbooks/{id}/lessons` | Return source-derived lesson boundaries. |
| `GET` | `/lessons/{id}` | Return one owner-scoped lesson. |
| `GET` | `/lessons/{id}/vocabulary` | Return vocabulary, meanings, source page, and review status. |
| `GET` | `/lessons/{id}/grammar` | Return grammar patterns, source page, and review status. |
| `GET` | `/lessons/{id}/exercises` | Return exercises/options/available answers and source page. |
| `GET` | `/lessons/{id}/sentences` | Return source-backed sentences. |
| `GET` | `/lessons/{id}/reading` | Return reading passages. |
| `GET` | `/lessons/{id}/listening` | Return track IDs and transcript availability; does not return fabricated audio. |

`POST /imports` body:

```json
{
  "source_path": "C:/approved-imports/textbook-1.pdf",
  "title": "Tiếng Hàn Tổng Hợp Sơ Cấp 1",
  "level": "beginner",
  "volume_number": 1
}
```

The response reports `already_imported: true` for byte-identical PDFs. New documents begin as `registered`; extraction begins only after `POST /imports/{id}/queue` and a separate worker run. `extracted` means raw source pages are present, not that human review has confirmed the content.

`rights_status` may be `unverified` (the default), `authorized`, or
`restricted`. Queueing raw extraction is allowed only when the status is
`authorized`; the worker independently enforces the same guard. This is
user-supplied metadata, not legal verification. The
structured extraction CLI reads a private raw JSON export and writes structured
JSON plus a quality report under `PRIVATE_STORAGE_ROOT`; it does not currently
write structured records to PostgreSQL as an automatic API/worker stage.
Structured persistence is tested as an internal service with synthetic
fixtures.

List endpoints for vocabulary, grammar, exercises, sentences, reading, and
listening accept `offset`, `limit` (1–100), and `review_status` query
parameters. `GET /health` is the only unauthenticated endpoint.
