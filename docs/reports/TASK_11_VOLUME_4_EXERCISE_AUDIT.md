# Task 11 - Trung cap 4 exercise content audit

## Result and scope

This is a private, candidate-level audit of the local Volume 4 PDF only. It
does not import any record, create an approved knowledge record, change the
schema, or modify the website. The private source and every raw/Marker output
remain ignored under `private-data/task11/`.

The audit uses the Task 10 integration baseline at `fa16137` (PR #12 is an
open draft, mergeable, with successful `api-postgres` and `web-build` checks).
No unmerged work was overwritten. The report branch is based on that exact
baseline.

Input checked locally:

- PDF: Volume 4, 338 PDF pages; SHA-256
  `82d68eb2e2c45b0b3dbaefa09092e14466584bc48d60970a92c679b9c82f05fc`.
- PyMuPDF raw extraction: 270 lesson pages (PDF 18-287), 6,502 text blocks,
  57,165 raw spans, 152 table candidates, and 1,199 image occurrences.
- Marker 2.0.0 fast layout sidecar: OCR disabled, no cloud/LLM,
  `--page_range 17-286` (Marker's zero-based numbering). It emitted 270
  pages, 3,626 top-level layout blocks, including 177 table blocks.
- Hybrid alignment: 4,220 of 5,003 flattened Marker blocks aligned to one or
  more PyMuPDF spans; 783 remain unresolved. All 177 Marker table blocks
  aligned geometrically; table recovery produced 2,833 cells (579 verified
  against raw table text, 239 recovered from raw spans, 1,488 needs review,
  and 527 missing). These are layout/provenance signals, not semantic accuracy
  claims.

Visual checks were performed on the two-page table of contents, the first
lesson cover, the appendix divider, and the first answer page. This confirmed
the PDF-versus-printed-page offset and that the answer appendix is source
material, rather than a generated answer source.

## Verified lesson boundaries

The table of contents supplies the 15 lesson starts in printed pages. Rendered
page review confirms that printed page 17 is PDF page 18, and that the
appendix divider is PDF page 288 (printed page 287). The final lesson therefore
ends at PDF page 287. A parser-only run emitted 20 "lessons", because it
mistook headings in the appendix for lessons; those five false positives are
excluded here.

| Lesson | Title | PDF pages | Printed pages |
|---:|---|---:|---:|
| 01 | 유행 | 18-35 | 17-34 |
| 02 | 집안일 | 36-53 | 35-52 |
| 03 | 감정 | 54-71 | 53-70 |
| 04 | 생활 정보 | 72-89 | 71-88 |
| 05 | 취직 | 90-107 | 89-106 |
| 06 | 고장 | 108-125 | 107-124 |
| 07 | 명절 | 126-143 | 125-142 |
| 08 | 여가 생활 | 144-161 | 143-160 |
| 09 | 직장 | 162-179 | 161-178 |
| 10 | 절약 | 180-197 | 179-196 |
| 11 | 결혼 | 198-215 | 197-214 |
| 12 | 사건과 사고 | 216-233 | 215-232 |
| 13 | 교육제도 | 234-251 | 233-250 |
| 14 | 생활과 환경 | 252-269 | 251-268 |
| 15 | 옛날이야기 | 270-287 | 269-286 |

The appendix divider is PDF 288. Listening material begins at PDF 289
(printed 288), the answer appendix at PDF 304 (printed 303), culture at PDF
318, and the new-word list at PDF 325.

## Candidate exercise inventory

The existing deterministic parser found 330 candidate exercise groups and 604
candidate questions in the validated lesson range. Each question carries a
preliminary source reference (`pdf_page_number` and `block_index`); none was
promoted to verified/approved content.

Classification below is conservative and rule-based. It combines the question
with its parent instruction: explicit blank/completion wording -> fill blank;
explicit selection wording or extracted options -> multiple choice; explicit
Korean/Vietnamese translation wording -> translation; explicit writing/open
response wording -> free response. Matching, ordering, listening, ambiguous
numbered material, and any weakly identified candidate remain `unsupported`.
Consequently this is an extraction queue, not a publishable question bank.

| Lesson | Groups | Questions | Fill blank | Multiple choice | Translation | Free response | Unsupported | Source answer | Needs review |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 01 | 23 | 45 | 8 | 15 | 0 | 11 | 11 | 0 | 45 |
| 02 | 24 | 46 | 2 | 7 | 0 | 22 | 15 | 0 | 46 |
| 03 | 21 | 41 | 10 | 2 | 0 | 17 | 12 | 0 | 41 |
| 04 | 22 | 46 | 9 | 6 | 1 | 20 | 10 | 0 | 46 |
| 05 | 23 | 39 | 4 | 9 | 0 | 15 | 11 | 0 | 39 |
| 06 | 21 | 41 | 4 | 3 | 0 | 17 | 17 | 0 | 41 |
| 07 | 19 | 27 | 13 | 2 | 0 | 9 | 3 | 0 | 27 |
| 08 | 22 | 42 | 7 | 6 | 0 | 13 | 16 | 0 | 42 |
| 09 | 21 | 40 | 10 | 6 | 0 | 17 | 7 | 0 | 40 |
| 10 | 21 | 39 | 15 | 4 | 0 | 10 | 10 | 0 | 39 |
| 11 | 21 | 38 | 9 | 7 | 0 | 13 | 9 | 0 | 38 |
| 12 | 23 | 41 | 4 | 9 | 0 | 17 | 11 | 0 | 41 |
| 13 | 21 | 39 | 10 | 7 | 0 | 18 | 4 | 0 | 39 |
| 14 | 23 | 37 | 11 | 1 | 0 | 21 | 4 | 0 | 37 |
| 15 | 25 | 43 | 9 | 8 | 0 | 16 | 10 | 0 | 43 |
| **Total** | **330** | **604** | **125** | **92** | **1** | **236** | **150** | **0** | **604** |

The table intentionally does not reproduce prompts, options, answers, raw
JSON, Markdown, or PDF images. Those stay in private storage. `Unsupported`
is an honest classification, not a failure converted into one of the four
requested types.

## Answers and review status

The answer appendix is present and visually confirmed at PDF 304-317. It
contains lesson/section/question-number hierarchies, but does not expose the
explicit global identifiers expected by the current answer linker. Reused
numbers across lesson sections make a positional automatic match unsafe.

Therefore the audit created **zero** answer links and marked all 604 candidate
questions as `needs_review`. It did not infer an answer, did not call an LLM,
and did not overwrite or create approved knowledge. The correct states are:

| State | Count / status |
|---|---|
| Extracted candidates | 604, with preliminary page/block provenance |
| Verified questions/answers | 0 (no question-level human verification performed) |
| Approved records | 0 (no import or review mutation performed) |
| Source answer links | 0 (ambiguous linkage deliberately withheld) |

## Parser and engine findings

1. Lesson segmentation must use the TOC/appendix boundary as a guard. The
   current detector produced 20 lessons and must not be used alone for this
   volume.
2. The real-layout exercise parser preserves many question candidates, but it
   cannot reliably distinguish all listening, matching, ordering, and free
   response subtypes from numbered layout alone. The full private run emitted
   933 warnings; those warnings are a review signal, not a reason to relax
   matching rules.
3. The answer linker only links explicit, unambiguous identifiers. The actual
   appendix requires a lesson + skill section + group + question mapping layer
   with independent source spans before answers can be attached safely.
4. Marker improves layout/table evidence but is not a semantic exercise parser:
   783 layout blocks remain unresolved and 2,015 recovered table cells are
   either missing or need review. Raw PyMuPDF spans remain canonical
   provenance.
5. Current exercise handling has no reviewed translation-direction field,
   rubric/schema for free response, matching/ordering model, or an answer-key
   resolver for the appendix hierarchy. Automatic grading must remain blocked
   unless an approved answer and, for multiple choice, complete approved
   options exist.

## Tests

No product code changed in this task; only this report is committed. Existing
regressions were still run on the integration baseline:

| Check | Result |
|---|---|
| API test suite | 43 passed, 4 skipped |
| Frontend unit suite | 2 files passed, 7 tests passed |
| Existing integration CI at baseline | PR #12 `api-postgres` and `web-build` successful (run `40199872263`) |

The task PR's CI is required before merging this report branch. This task does
not claim a new PostgreSQL import, because no knowledge records were persisted.

## Recommendation for Task 12

Build a review-first answer-resolution workflow, not automatic answer import:

1. Persist the verified 15 lesson boundaries as source metadata.
2. Add a private reviewer queue that displays lesson, skill section, group,
   question, candidate answer, and both source spans side by side.
3. Require a reviewer-confirmed compound key before creating an `AnswerKey`;
   leave ambiguous rows unresolved.
4. Add typed models/review rules for matching, ordering, listening, and
   translation direction before attempting learner delivery or grading.
5. Create a small, licensed, manually labelled ground-truth sample before
   changing parser heuristics or reporting precision/recall.

## Remaining risks

- Counts are extraction candidates, not semantic ground truth.
- No question/answer pair is verified or approved yet.
- OCR was intentionally disabled; image-only prompt regions remain unresolved.
- This audit is restricted to the private local copy of Volume 4 and must not
  be interpreted as permission to redistribute its text or answers.
