# Task 12.1 — Volume 4 Lesson 01 Exercise Acceptance

## Scope and source handling

This acceptance run used the authorized, local-only Volume 4 PDF. It processed
lesson pages 18–35 and answer-appendix pages 304–317 into an ignored private
store. The PDF, rendered images, Marker Markdown/JSON, database, and review
notes are not tracked by Git.

The run uses the existing PyMuPDF worker plus Marker 2.0.0 in fast mode with
OCR disabled and Marker range `17-34` (the required zero-based equivalent of
PDF pages 18–35). Marker emitted 18 Markdown pages and JSON sidecar output.
Raw PyMuPDF source spans remain canonical provenance; Marker was used only as
layout corroboration.

## Candidate disposition

Task 11's private inventory contains 45 preliminary Lesson 01 questions. The
number is an extraction inventory, not a semantic-quality claim. This task
did not bulk-promote it:

| Disposition | Count | Learner treatment |
|---|---:|---|
| Multiple choice, source and option order verified | 2 | Approved and automatically graded only with an approved answer key |
| Vietnamese-to-Korean translation, source and reference verified | 1 | Approved; source reference is shown after submission, never exact-string graded |
| Fill/completion prompt, source verified | 1 | Approved for submission; no answer key was approved, so it remains pending review |
| Free response prompt, source verified | 1 | Approved for submission; never auto-graded |
| Withheld | 40 | Not published. This includes listening/media-dependent, asset-dependent, ambiguous, or insufficiently matched candidates; withholding is not a claim that every item is invalid. |

The five published items retain source page/block provenance. No title, passage,
or option text was synthesized. The candidate list is intentionally not copied
to this report because it contains private textbook material.

## Import, matching, and review evidence

- One `SourceDocument` was registered for the PDF; import jobs were created
  for ranges 18–35 and 304–317.
- Re-importing both ranges returned the existing range-specific jobs and did
  not duplicate source pages, lessons, exercises, answer keys, or attempts.
- The final isolated acceptance database contains 32 unique source pages, one
  Lesson 01 record, five approved exercises, and three approved source-backed
  answer records.
- Two multiple-choice answers and one translation reference were matched using
  the complete volume/lesson/skill/group/question compound key. Each candidate
  was confirmed and approved through the answer-resolution review workflow.
- The other two learner submissions deliberately have no answer key. They
  return `pending_review`, rather than an invented score.
- Direct review actions require page, source text, position, semantic
  alignment, and structure checks. Every published exercise and option has
  matching provenance before approval.

## Corrections made during acceptance

1. `SessionLocal` disables autoflush. Repeated source evidence for the same
   option in one extraction transaction could schedule duplicate provenance
   rows and fail with a database unique constraint. Persistence now checks
   pending provenance rows before adding another record.
2. The appendix divider in this Vietnamese/Korean source was marked as a
   header candidate and used the Vietnamese label for an answer key. Lesson
   segmentation now recognizes that label even when it is a header candidate,
   preventing answer-appendix headings from becoming false lessons.
3. Exercises can now carry an interaction configuration. The learner UI uses
   separate fields for multi-blank prompts, text areas for translation/free
   response, source-page labels, and status-specific feedback. The study API
   does not exact-string-grade translations or free responses.

## Tests and browser acceptance

| Check | Result |
|---|---|
| Focused parser and lesson acceptance regressions | 14 passed |
| Full API suite | 53 passed, 4 skipped |
| Alembic upgrade → downgrade → upgrade | passed; head `20261026_0012` |
| Frontend unit tests | 2 files, 7 tests passed |
| Next.js production build | passed |
| Production dependency audit | 0 vulnerabilities |
| Private real-PDF acceptance | passed in a separate ignored database: source pages, re-import idempotency, review states, answer matching, and learner submissions asserted |
| Browser acceptance | Signed in to a local private server; Lesson 01 exposed exactly five approved exercises and a verified multiple-choice submission displayed the sourced correct result |

PostgreSQL 16 validation is supplied by the GitHub Actions `api-postgres`
check for the task PR. Local SQLite acceptance proves the real-PDF workflow
and does not substitute for that CI result.

## Remaining risks

- Forty withheld candidates still need item-level review before learner
  publication.
- OCR remains off; image-only and listening-dependent prompts are not
  accepted by this task.
- Marker layout output is corroborating evidence, not a replacement for
  PyMuPDF source spans or human review.
- The task branch must not be merged until the new PostgreSQL and web checks
  are green.
