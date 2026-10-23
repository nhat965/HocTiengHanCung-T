# PDF extraction report — Task 01

## Source audit

The user-provided *Tiếng Hàn Tổng Hợp Trung Cấp 4* PDF was inspected with Poppler metadata tooling on 2026-10-23.

- PDF pages: **338**
- Encryption: **none**
- PDF is readable by metadata inspection: **yes**
- Pilot target: Bài 01 — 유행, book pages 17–34

## Pilot status

**A bounded raw pilot was executed** on volume 4, lesson 01: PDF pages 18–35,
corresponding to printed pages 17–34. It yielded 18 pages, 419 text blocks,
3,735 spans, 14 detected table candidates, and 54 extracted images. No
structured knowledge records were persisted or claimed as extracted.

## Task 01A implementation

The extractor emits per-page raw text, block and span coordinates, font attributes, page dimensions and rotation, detected table rows, extracted image assets and their placement metadata. The JSON also records PDF metadata, file size, page count, and SHA-256. OCR remains an indicator only; this tool does not claim to perform OCR.

The local pilot output is `data/extracted/book-4/lesson-01-raw.json` with an
adjacent image-assets directory. It is ignored by Git because it contains
source textbook content. The six-source audit is documented in
[`reports/SOURCE_PDF_AUDIT.md`](./reports/SOURCE_PDF_AUDIT.md), and measured
pilot counts are in [`reports/EXTRACTION_RESULTS.md`](./reports/EXTRACTION_RESULTS.md).

Run from `apps/api`:

```powershell
python -m app.extract_pdf "C:\path\to\source.pdf" --output "artifacts\source.json"
```

The command writes image files into a sibling `source_assets` directory. API tests use the bundled runtime in this checkout:

```powershell
..\..\.tools\python311\python.exe -m pytest tests
```

## Remaining work

- Visually inspect and correct the pilot's reading order, table alignment, and section boundaries against the PDF.
- Add region-level OCR review flags and configure an OCR provider with Korean and Vietnamese language support.
- Add structured lesson-content extraction and source relationships in Task 01B.
- Add transcript/answer-key matching, missing-data checks, and review tooling in Task 01C.
- Verify PostgreSQL migrations and worker operation against a live database.
