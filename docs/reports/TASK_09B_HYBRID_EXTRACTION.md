# Task 09B - Hybrid PDF Knowledge Extraction

## 1. Architecture

Task 09B adds an opt-in sidecar under
`apps/api/app/services/hybrid_extraction/`. The existing PyMuPDF engine remains
the canonical raw source and the existing knowledge parsers and persistence
layer remain authoritative:

`raw PDF -> existing raw pages/spans -> Marker layout sidecar -> alignment -> table recovery -> existing knowledge pipeline -> review/persistence`

No database schema, learner API, frontend, or import-worker claim/lease logic
was changed. Marker output is never auto-approved and OCR output is never
inserted into the knowledge bundle automatically.

## 2. Marker configuration

- Marker `marker-pdf` 2.0.0.
- `--mode fast --disable_ocr --disable_multiprocessing`.
- Local CPU-only environment, no LLM/cloud calls.
- Pilot input: authorized local Volume 4 pages 18-35 (18 pages); Marker page
  range `17-34`.
- Marker page IDs are converted from zero-based to the application's one-based
  `pdf_page_number`.

The reusable pilot command is `tools/run_marker_pilot.ps1`. Generated PDF,
Markdown, JSON, image, and reference-render files remain ignored under
`private-data/marker-pilot/` and are not part of this report or commit.

## 3. Existing engine integration

`marker_adapter.py` parses Marker JSON into an internal layout schema that
retains Marker IDs, HTML, polygons, bounding boxes, page indexes, and section
hierarchy. `layout_alignment.py` maps each block to zero or more existing raw
spans using page mapping, scaled geometry, and conservative text comparison.
One layout block can reference multiple raw spans; an ambiguous or missing
match is `unresolved`, never a fabricated source span.

`knowledge_bridge.py` calls the existing `extract_knowledge` implementation
after table recovery. No parallel vocabulary, grammar, dialogue, reading, or
exercise parser was introduced.

## 4. Vocabulary table recovery

`table_recovery.py` parses Marker table HTML, identifies the corresponding raw
table by polygon overlap, groups raw spans by row and column, and merges only
source-backed values. Existing raw table values always win. Each recovered cell
retains its raw span references and is classified as `verified`, `recovered`,
`needs_review`, or `missing`.

The algorithm does not infer Vietnamese meanings, copy values between rows, or
delete unmatched spans. A synthetic ground-truth regression fixture verifies
two Korean-Vietnamese pairs, row separation for close rows, and source-span
links for recovered cells. The real pilot produced recovered cells only where
raw spans provided direct evidence; remaining cells stayed review-required.

## 5. Provenance mapping

`provenance.py` resolves aligned raw references to persisted
`SourcePage`/`SourceBlock`/`SourceSpan` IDs when exactly one database row
matches. Multiple matches and missing pages remain unresolved. This prevents a
Marker block from being attached to the first similar span by accident.

The bridge preserves the existing `SourceRef` values used by
`knowledge.persistence.persist_bundle`, so existing duplicate protection,
approved-content preservation, review history, and learner-progress behavior
remain unchanged.

## 6. OCR fallback and limitations

`ocr_fallback.py` plans OCR only for image regions with missing text-layer
evidence. It uses the existing `OcrAdapter` contract and the safe
`DisabledOcrAdapter` by default. OCR outcomes retain page, image, and bounding
box provenance. Unavailable or failed OCR is `unresolved`; it cannot create
answers, meanings, transcripts, or approved learner content.

No production OCR backend was available in this environment. The unavailable
adapter path is covered by a regression test and is reported as a blocker for
OCR acceptance, not as successful OCR on the textbook.

## 7. Knowledge and quality results

The real pilot was executed on the same 18-page range as Task 09A:

| Metric | Result |
|---|---:|
| Raw pages processed | 18 |
| Marker layout blocks | 344 |
| Blocks aligned to raw spans | 279 |
| Unresolved layout blocks | 65 |
| Marker tables connected to raw tables | 10 |
| Cells recovered from raw spans | 8 |
| Cells still missing/needs review | 130 |
| Vocabulary records passed to existing parser | 59 |
| Vietnamese meanings passed to existing parser | 59 |
| Lessons / sections | 1 / 12 |
| Grammar patterns / example sentences | 3 / 24 |
| Dialogue turns / reading passages | 17 / 4 |
| Exercise questions | 42 |
| Exercise records / options | 67 / 27 |
| Listening tracks / sourced transcripts | 5 / 0 |
| Sourced answer keys | 0 |
| OCR regions attempted in real pilot | 0 |

These are deterministic output counts, not precision, recall, or accuracy.
There is no independent licensed ground-truth set for the complete page range,
so no accuracy percentage is claimed. All extracted records retain the
existing pending/unverified review defaults.

## 8. PostgreSQL and persistence

No Alembic migration was needed. The hybrid result is a bridge into the
existing `persist_bundle` transaction and therefore uses the established
SourceDocument/SourcePage uniqueness, idempotent knowledge keys, provenance,
review, and learning-state preservation rules. Existing API tests cover
approved-content preservation, manual corrections, progress, study attempts,
rollback, duplicate prevention, and owner isolation.

The local test environment used SQLite because no PostgreSQL server/client was
available on this workstation. PostgreSQL 16 migration and integration
verification remains a CI acceptance requirement.
Alembic `upgrade head -> downgrade base -> upgrade head` passed against an
in-memory SQLite database; this checks migration ordering, not PostgreSQL
compatibility.

## 9. Real-PDF comparison

For pages 18-35, Task 09A measured the existing engine at 419 text blocks,
3,735 spans, 14 table candidates, and 54 image records. The hybrid run keeps
those raw records as source-of-truth and adds Marker's 344 layout blocks and
polygon coordinates. The table bridge recovered only direct raw-span evidence;
it did not treat Marker-only text as verified. This is safer than accepting the
Marker standalone loss of Vietnamese table cells, but still requires human
review for the remaining cells and image-only exercise content.

The hybrid pipeline therefore improves layout and recovery signals without
replacing the existing engine or claiming semantic correctness.

## 10. Regression test evidence

Added `apps/api/tests/test_hybrid_extraction.py` covering:

1. Marker zero-based to one-based page mapping.
2. One Marker block aligned to multiple source spans.
3. Vietnamese table-cell recovery from raw spans with provenance.
4. Close table rows kept separate.
5. OCR-unavailable regions remaining unresolved and review-only.
6. Existing exercise parser reuse, option ordering, and no invented answer.

Results:

- Targeted hybrid tests: **6 passed**.
- Full API suite: **43 passed, 4 skipped** (local SQLite).
- Alembic/PostgreSQL CI: pending on the pushed PR.

## 11. Performance

The Marker sidecar from Task 09A ran in 11.69 seconds for Markdown and 7.39
seconds for JSON on 12 logical CPU cores with 15.19 GiB visible RAM. The
hybrid alignment and recovery pass is in-process, bounded to the requested
page range, and does not load all six PDFs. Marker model/font downloads remain
an environment/deployment concern.

## 12. Commit and CI

- Base: Task 09A pilot commit `c6a9c01`.
- Task 09B implementation commit SHA: `e904acb`.
- Pull request: pending GitHub authentication.
- GitHub Actions URL: pending push.

## 13. Remaining issues

- Table recovery still requires review for cells without unique raw-span
  evidence; it deliberately prefers unresolved output over guessed meanings.
- OCR backend/inference policy is not available locally and was not claimed as
  working on the real textbook.
- Marker block polygons are not character-level provenance; the existing raw
  spans remain canonical.
- Complete semantic precision/recall and learner-ready acceptance require a
  licensed, independently reviewed ground-truth set.
- PostgreSQL 16 and migration checks must pass in CI before this branch is
  considered mergeable.

**Conclusion:** The hybrid adapter is safe to review as an opt-in extraction
sidecar. It is not a replacement for the current PDF engine, and no content is
learner-facing until the existing review workflow approves it.

