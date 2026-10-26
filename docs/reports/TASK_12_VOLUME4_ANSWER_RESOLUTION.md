# Task 12 — Volume 4 Answer Key Resolution

## Scope and baseline

This task implements a review-first answer-resolution pipeline for the local
Volume 4 PDF only.  It is based on Task 11 commit `7721ad0` (itself based on
the Task 10 integration baseline `fa16137` / PR #12).  `master`, PR #12 and
PR #13 were inspected before the branch was created; no pull request was
merged or rebased.

The private input is the 338-page Volume 4 PDF already present in the local
workspace.  Lesson pages are PDF 18–287 and the answer appendix is PDF
304–317.  The PDF, rendered pages, raw extraction, Marker sidecars and answer
text stay in ignored private storage; this report intentionally contains no
reproducible textbook content.

## What was built

The pipeline is deliberately conservative:

`appendix source span → AnswerResolutionCandidate → exact compound-key match → reviewer confirmation → approved AnswerKey`

The compound key contains all five required components:

`volume + lesson + skill_section + exercise_group + question_number`

Two new records carry the independent source evidence:

- `ExerciseAnswerContext` stores one source-backed question identity per
  exercise and source document.
- `AnswerResolutionCandidate` stores a proposed appendix answer, its source
  span, match status, reviewer note and version.

Both records are unique/idempotent at their evidence boundary.  A different
compound key for an already-mapped exercise is rejected instead of creating a
duplicate context.  The persistence batch uses a nested transaction, validates
both document ownership and spans, and rolls back all newly added contexts and
candidates on error.

The candidate lifecycle is `extracted`, `matched_candidate`, `needs_review`,
`verified`, `approved`, or `unresolved`.  A match is never published as a
learner answer.  Only a reviewer-confirmed candidate with all five source and
structure checks can create an approved `AnswerKey`.

The reviewer page now shows the lesson, skill, group, question number,
question text/provenance, appendix candidate/provenance, status and reason.
Reviewers can confirm, reject, or explicitly remap a candidate to a
source-backed question context (with a required note), then complete the
checklist before approval.  Review history, source provenance and optimistic
version checks are written for review actions.  The API refuses to overwrite
an approved or human-corrected answer.

## Private PDF extraction and Bài 01 ground truth

The appendix was parsed from 660 PyMuPDF raw blocks on PDF 304–317.  It
produced 437 source-backed answer fragments: 369 have every compound-key
component available from the local appendix layout and 68 remain incomplete
and therefore unresolved.  These are extraction counts, **not accuracy
claims** and were not bulk imported into approved knowledge.

Task 11 supplies 604 unverified question candidates for the fifteen validated
lessons.  This task leaves their review state unchanged until an operator adds
the corresponding source-backed question contexts.  Hence the private run has
zero automatically persisted/verified/approved pairs.  That is intentional:
the appendix visual order sometimes places a skill/group block before its
lesson label, and number reuse makes positional association unsafe.

Manual Bài 01 checks were performed against the rendered source pages and raw
block references.  They validate the review inputs, not an automatic approval:

| Sample | Question evidence | Appendix evidence | Result |
|---|---|---|---|
| Reading group 1, questions 1–2 (reused local numbering) | PDF 28, raw blocks 2, 5–6 | PDF 304, raw block 3 | Candidate hierarchy is reviewable; each answer fragment is bounded by the next question marker. |
| Reading group 2, questions 1–2 (multiple choice) | PDF 28, raw blocks 7, 14–19 | PDF 304, raw block 5 | Same question numbers are kept distinct by group; no option is approved until its option mapping is reviewed. |
| Reading group 3, questions 1–2 (multiple choice) | PDF 29, rendered visual review | PDF 304, raw block 6 | Repeated question numbers across groups do not cross-match. |
| Speaking/writing open-response and completion prompts | PDF 24/27/31/33, source blocks in the private audit | No unambiguous Appendix mapping claimed | Kept `unresolved`; a free response without a verified source answer requires manual review. |

The Bài 01 inventory in Task 11 includes fill/completion, multiple choice and
free-response candidates; it has no verified translation candidate.  This task
does not manufacture a translation example.  It also does not convert a
free-response prompt into an automatically gradeable answer.

## Compatibility and safeguards

- Fill blank answers are stored only as source-backed reference text; no
  synonyms or variants are generated.
- Multiple choice remains blocked by the existing learner API unless approved
  answer keys and a complete set of approved options exist.
- Translation references can be persisted with their source but no
  exact-string grading policy is introduced here.
- Free responses without a verified source answer remain unresolved/manual
  review; no AI grading was added.
- Existing approved records, human corrections, learning progress and study
  attempts are not deleted or reset.  The resolver only creates an approved
  `AnswerKey` after review and refuses conflicting approved/manual values.

## Files changed

- `apps/api/app/models.py` — answer-context and answer-candidate models.
- `apps/api/migrations/versions/20261026_0011_answer_resolution.py` — a single
  Alembic migration after revision `20261024_0010`.
- `apps/api/app/services/answer_resolution.py` — conservative parser,
  provenance validation, idempotent transactional persistence.
- `apps/api/app/routers/answer_resolution.py` and `schemas.py` — private
  reviewer queue, confirmation/rejection/remapping and guarded approval API.
- `apps/api/app/main.py` — router registration.
- `apps/web/app/review/page.tsx` — source-evidence review controls and a
  required approval checklist.
- `apps/api/tests/test_answer_resolution.py` — resolver regressions.
- `.github/workflows/task-03.yml` — run the existing PostgreSQL/API and web
  CI jobs for every pull request, rather than only an obsolete branch allowlist.

## Regression coverage and results

| Requirement | Coverage |
|---|---|
| Same lesson/group question matches | Exact compound-key resolver test |
| Reused question number in two groups | Separate group test |
| Missing answer | Unresolved candidate test |
| Multiple candidates | Needs-review test |
| Reviewer confirm and reject | API workflow tests |
| Approved/human correction preserved | Conflict test |
| Learner grading stays blocked until approval | Study-attempt assertion |
| Re-import idempotency/no duplicate context | Resolver re-import and changed-key test |
| Transaction rollback | Invalid answer-span rollback test |

Local verification completed before commit:

| Check | Result |
|---|---|
| Targeted resolver regression suite | 8 passed |
| Full API suite | 51 passed, 4 skipped |
| Alembic on SQLite | upgrade → downgrade → upgrade completed; head `20261026_0011` |
| Frontend unit suite | 2 files / 7 tests passed |
| Next.js production build | passed |

Docker is not installed in this local environment, so PostgreSQL 16 validation
is delegated to the existing GitHub Actions `api-postgres` job after the branch
is pushed.  The workflow's former pull-request branch allowlist would have
silently skipped this Task 12 PR, so it is removed as a small CI-only fix.  The
Task 12 CI completed successfully for commit
`5cccfca553af1f820183c191df094d5dffc90f23`:

- [API/PostgreSQL 16 job](https://github.com/nhat965/HocTiengHanCung-T/actions/runs/40262869881/job/121378785157)
  — successful.
- [Web tests and production build](https://github.com/nhat965/HocTiengHanCung-T/actions/runs/40262869881/job/121378785431)
  — successful.

The report-only commit following this section preserves the same validated
implementation and triggers the final PR check on the branch head.

## Remaining risks

1. The actual appendix has multi-column/layout ordering ambiguities.  The 68
   incomplete candidates remain unresolved by design and require reviewer
   source selection.
2. Task 11 question candidates are unverified extraction output.  A reviewer
   must first create/confirm source-backed contexts before any private answer
   candidate can reach `verified`.
3. Some answer lines have rich multi-part structures.  The parser separates
   only explicitly marked question fragments; it never guesses omitted
   boundaries.
4. OCR/image-only regions, AI grading, audio/video, and all other volumes are
   outside this task.
