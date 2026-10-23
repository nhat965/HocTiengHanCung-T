# API (Phase 1)

Base URL: `http://localhost:8000/api/v1`

| Method | Path | Purpose |
| --- | --- | --- |
| `GET` | `/health` | Liveness and database availability check. |
| `GET` | `/textbooks` | List imported textbook records. |
| `POST` | `/imports` | Start an idempotent import from a server-visible PDF path. |
| `GET` | `/imports/{id}` | Retrieve import-job state. |

`POST /imports` body:

```json
{
  "source_path": "C:/approved-imports/textbook-1.pdf",
  "title": "Tiếng Hàn Tổng Hợp Sơ Cấp 1",
  "level": "beginner",
  "volume_number": 1
}
```

The response reports `already_imported: true` for byte-identical PDFs. The importer does not claim lesson extraction completed until its job state is `completed` and reviewed output exists.
