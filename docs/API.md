# API (Phase 1)

Base URL: `http://localhost:8000/api/v1`

| Method | Path | Purpose |
| --- | --- | --- |
| `GET` | `/health` | Liveness and database availability check. |
| `GET` | `/textbooks` | List imported textbook records. |
| `POST` | `/imports` | Start an idempotent import from a server-visible PDF path. |
| `POST` | `/imports/{id}/queue` | Queue a registered/retryable import for the worker. |
| `GET` | `/imports/{id}` | Retrieve import-job state. |
| `GET` | `/imports/{id}/report` | Return coverage/accuracy-separated extraction metrics. |
| `GET` | `/textbooks/{id}/lessons` | Return source-derived lesson boundaries. |
| `GET` | `/lessons/{id}` | Return one lesson. |
| `GET` | `/lessons/{id}/vocabulary` | Return reviewed or pending source-backed vocabulary. |
| `GET` | `/lessons/{id}/grammar` | Return reviewed or pending source-backed grammar. |
| `GET` | `/lessons/{id}/exercises` | Return source-backed exercises. |

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
