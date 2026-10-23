# PDF extraction report — Task 01

## Source audit

The user-provided *Tiếng Hàn Tổng Hợp Trung Cấp 4* PDF was inspected with Poppler metadata tooling on 2026-10-23.

- PDF pages: **338**
- Encryption: **none**
- PDF is readable by metadata inspection: **yes**
- Pilot target: Bài 01 — 유행, book pages 17–34

## Pilot status

**Not executed.** The extraction engine was tested with a synthetic PDF fixture; the textbook pilot has not been run. No textbook lesson content has been persisted or claimed as extracted, and this report intentionally includes no vocabulary, grammar, dialogue, transcript, or answer keys copied from the source.

## Task 01A implementation

The extractor emits per-page raw text, block and span coordinates, font attributes, page dimensions and rotation, detected table rows, extracted image assets and their placement metadata. The JSON also records PDF metadata, file size, page count, and SHA-256. OCR remains an indicator only; this tool does not claim to perform OCR.

Run from `apps/api`:

```powershell
python -m app.extract_pdf "C:\path\to\source.pdf" --output "artifacts\source.json"
```

The command writes image files into a sibling `source_assets` directory. API tests use the bundled runtime in this checkout:

```powershell
..\..\.tools\python311\python.exe -m pytest tests
```

## Remaining work

- Run and manually inspect a rights-cleared textbook pilot, then record extraction coverage and errors.
- Add structured lesson-content extraction and source relationships in Task 01B.
- Add transcript/answer-key matching, missing-data checks, and review tooling in Task 01C.
- Verify PostgreSQL migrations and worker operation against a live database.
