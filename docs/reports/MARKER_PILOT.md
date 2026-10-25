# Task 09A — Marker PDF Extraction Pilot

## Scope and reproducibility

This is an offline pilot only. It does not replace the current PDF engine,
change the import workflow, or write to the application database.

- Source: local Volume 4 PDF, Lesson 01 (`유행`).
- PDF pages: 18–35, 1-based (18 pages).
- Marker range: `--page_range 17-34`, 0-based.
- Mode: `--mode fast --disable_ocr --disable_multiprocessing`.
- LLM/cloud: disabled; no `--use_llm` and no API keys.
- Outputs: ignored local files under `private-data/marker-pilot/`.
- Re-run helper: `tools/run_marker_pilot.ps1`.

The PDF and generated Markdown, JSON, images, and reference renders are not
tracked or committed. The report contains aggregate measurements only and no
textbook excerpts.

## Marker version and machine

- `marker-pdf`: 2.0.0
- Python: 3.12.14
- PyTorch: 2.14.1+cpu
- OS: Windows 11
- CPU: 12 logical CPUs (AMD64)
- RAM: 15.19 GiB visible to the runtime
- CUDA: unavailable; CPU-only run
- Runtime environment: separate `C:\marker-pilot-venv` virtual environment.

Marker 2.0.0 downloaded its runtime font on first use. The first venv under
the Unicode workspace path failed while loading an OpenBLAS DLL through
`threadpoolctl`; the same package and command succeeded from the ASCII path
above. This is an environment/path limitation, not a PDF extraction result.

## Execution

| Output | Result | Runtime |
|---|---:|---:|
| Markdown + extracted images | completed | 11.69 s |
| JSON + block polygons | completed | 7.39 s |

All 18 requested pages were emitted. Marker JSON page IDs are 0-based
(`/page/17` through `/page/34`), so an adapter must add one before linking to
the application `pdf_page_number` field.

## Aggregate output

| Measurement | Marker fast/no-OCR | Current PDF Engine |
|---|---:|---:|
| Pages | 18 | 18 |
| Non-page layout blocks | 344 | 419 text blocks |
| Text/line blocks | 176 (`Text` 116, `Line` 60) | 3,735 spans |
| Table blocks/candidates | 15 | 14 |
| Picture blocks/images exported | 16 | 54 image records |
| Blocks with polygon provenance | 344 / 344 | block bboxes and page spans |
| Full extracted character count (descriptive) | 12,665 | 13,391 |
| Hangul character count (descriptive) | 5,614 | 5,897 |
| Latin character count (descriptive) | 1,615 | 1,949 |
| Vietnamese diacritic count (descriptive) | 657 | 774 |

These are engine-output comparisons, not precision, recall, or accuracy. No
formal ground-truth dataset was available, so no accuracy percentage is
claimed.

## Page-by-page check

The rendered source pages and both Marker formats were checked for all 18
pages. Character counts below are a diagnostic comparison with the existing
raw pilot, not a correctness score.

| PDF page | Marker page | Marker blocks | Tables | Pictures | Marker chars / old chars |
|---:|---:|---:|---:|---:|---:|
| 18 | 17 | 8 | 0 | 1 | 534 / 522 |
| 19 | 18 | 33 | 4 | 0 | 714 / 1,126 |
| 20 | 19 | 21 | 1 | 0 | 1,327 / 1,226 |
| 21 | 20 | 11 | 1 | 0 | 1,291 / 1,231 |
| 22 | 21 | 28 | 0 | 9 | 453 / 1,041 |
| 23 | 22 | 8 | 2 | 1 | 600 / 544 |
| 24 | 23 | 36 | 2 | 0 | 743 / 720 |
| 25 | 24 | 13 | 0 | 0 | 762 / 739 |
| 26 | 25 | 12 | 1 | 2 | 448 / 419 |
| 27 | 26 | 6 | 0 | 0 | 154 / 145 |
| 28 | 27 | 17 | 1 | 0 | 729 / 748 |
| 29 | 28 | 8 | 0 | 0 | 672 / 705 |
| 30 | 29 | 16 | 0 | 1 | 1,149 / 1,196 |
| 31 | 30 | 19 | 1 | 0 | 774 / 724 |
| 32 | 31 | 14 | 1 | 0 | 126 / 128 |
| 33 | 32 | 22 | 1 | 1 | 304 / 331 |
| 34 | 33 | 21 | 0 | 1 | 1,147 / 1,201 |
| 35 | 34 | 51 | 0 | 0 | 738 / 645 |

## Manual comparison findings

Manual review used rendered source pages 18, 19, 22, 24, 28, and 35 as a
representative sample of the cover, vocabulary tables, picture-heavy speaking
exercises, listening questions, reading content, and glossary layout. The
remaining pages were checked through page-by-page JSON/Markdown structure and
rendered contact-sheet review.

### Strengths

- Correctly processed all 18 requested pages with stable page IDs and polygon
  coordinates for every emitted non-page block.
- Preserved reading order well for ordinary Korean/Vietnamese paragraphs,
  grammar explanations, listening question text, and glossary columns.
- Detected table structure on most text-layer tables, including a course-info
  table that the current engine did not report as a table candidate.
- Preserved ordered list items and circled-choice text on the listening page;
  this is useful as a layout signal for later exercise parsing.
- Extracted picture blocks and wrote image assets without enabling OCR.

### Losses and structural risks

- The vocabulary page's four tables were detected, but the Markdown/JSON table
  cells retained much of the Korean while dropping most Vietnamese translation
  cells. This is a material knowledge loss, not just formatting variation.
- Picture-heavy speaking pages preserved the pictures and nearby text but did
  not recover text embedded inside those pictures when OCR was disabled. Blank
  prompts and visual answer cues therefore remain incomplete.
- Marker classifies blocks as `SectionHeader`, `Text`, `ListItem`, `Table`,
  `Picture`, and similar layout types; it does not distinguish instruction,
  question, option, answer, dialogue, or exercise semantics by itself.
- Circled choices that exist in the PDF text layer retained their order, but
  choices rendered only inside images were unavailable without OCR.
- JSON polygons provide block-level position provenance, but there are no
  current-engine-style character spans and the page numbering is 0-based.
  An integration adapter would need explicit 0-to-1-based mapping and source
  document IDs.
- The current engine emits more granular spans and image records, while Marker
  emits fewer larger layout blocks. The two outputs are not interchangeable.

## Comparison with current PDF Engine

The current engine remains stronger for this website's source-of-truth layer:
it produced 419 text blocks, 3,735 spans, 14 table candidates, 54 image
records, and 1-based page records for the same range. Marker produced cleaner
high-level layout blocks and stronger polygon provenance, but its no-OCR fast
path lost Vietnamese table content and image-only exercise content.

## Conclusion

Do not integrate Marker as the primary extraction engine or replace the current
engine based on this pilot. Marker is promising as an optional, offline layout
sidecar for block/table discovery and paragraph ordering, provided a future
phase adds a provenance adapter, table-cell completeness checks, image/OCR
coverage tests, and a licensed ground-truth set. Any such phase must retain
the current engine as the canonical source until those checks pass.

## Remaining risks

- No formal precision/recall/coverage score can be reported without reviewed
  ground truth.
- OCR-on behavior was intentionally not evaluated in this task; it may recover
  image text but changes runtime and inference requirements.
- Marker model/font downloads and CPU memory requirements need a deployment
  policy before any production use.
- Private pilot outputs remain local and ignored; they are not available to CI
  or reviewers unless regenerated in an authorized environment.
