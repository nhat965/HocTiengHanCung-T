# Task 12.1 - Volume 4 Lesson 01 Exercise Acceptance

## Scope and evidence

The acceptance run used the authorized local Volume 4 PDF, lesson pages 18-35
and answer-appendix pages 304-317. The PDF, rendered pages, Marker output,
candidate ledger, acceptance database, and review notes stay under ignored
private storage and are not tracked by Git.

The existing PyMuPDF worker remains the canonical source of page/block spans.
Marker 2.0.0 ran in fast mode with OCR disabled over zero-based range `17-34`
and produced 18 Markdown pages plus JSON sidecars for layout corroboration.
No textbook text was copied into this report or public fixtures.

## Audit of the 45 Task 11 candidates

Every candidate was matched back to its rendered PDF page and source block.
The private ledger asserts that all ordinals 1-45 are present exactly once.
This is a semantic audit, separate from parser labels and application review
status.

| Source disposition | Count | Treatment |
|---|---:|---|
| Valid question | 17 | 3 accepted from the original inventory; 14 remain `needs_review` |
| Parser false positive | 2 | Withheld |
| Incomplete question/options | 4 | Withheld until grouping/options are repaired |
| Requires image/context asset | 8 | Withheld; OCR and image exercises are out of scope |
| Unsupported listening/table interaction | 14 | Withheld |
| **Total** | **45** | **3 accepted, 14 need review, 28 withheld** |

Two additional real questions missed by the Task 11 candidate inventory were
recovered directly from source spans: one Vietnamese-to-Korean translation and
one free-response writing prompt. Therefore, five source-backed exercises are
present in the acceptance database, but only three of those five came from the
original set of 45. The earlier shortcut `45 - 5 = 40` is invalid; the exact
number of original candidates not learner-ready is **42**.

## Accepted vertical slice

| Metric | Count |
|---|---:|
| Initial Task 11 candidates | 45 |
| Semantically valid candidates | 17 |
| Valid original candidates accepted | 3 |
| Real parser misses recovered | 2 |
| Source-backed exercises in acceptance DB | 5 |
| Fill blank/completion | 1 |
| Multiple choice | 2 |
| Translation | 1 |
| Free response | 1 |
| Multiple-choice items with complete ordered options | 2 |
| Exercises with appendix answer/reference source | 3 |
| Exercise review actions recorded | 5 |
| Answer mappings confirmed and approved | 3 |
| Application records with `approved` status | 5 |
| Learner-ready submissions | 5 |
| Automatically graded submissions | 2 |
| Reference-only, never exact-string graded | 1 |
| Pending manual evaluation after submission | 2 |
| Original candidates still `needs_review` | 14 |
| Original candidates withheld as non-ready | 28 |
| Original candidates not learner-ready | 42 |

The owner-scoped review workflow recorded explicit source checks and audit
history for the five exercises and three answer mappings. This is an
agent-assisted acceptance run under the task's local owner identity, not a
claim that a second independent human reviewer signed off. A future human
reviewer can inspect the page/span, options, appendix source, checks, notes,
and versioned history and can correct, reject, or re-approve each record.

The two multiple-choice questions are graded only because their prompt,
ordered option set, and appendix answer are all approved. The translation
shows an approved source reference after submission but never uses exact-match
grading. The fill/completion and free-response exercises accept and retain a
learner response but return `pending_review`; no answer is invented.

## Import, provenance, and data safety

- One `SourceDocument` represents the PDF; separate import jobs cover 18-35
  and 304-317.
- Re-import returns the existing range-specific job and does not duplicate
  source pages, lessons, exercises, answer keys, or attempts.
- The isolated database contains 32 unique source pages and exactly one Lesson
  01 record for pages 18-35. The appendix does not create false lessons.
- All five exercises retain source-span provenance. The three appendix matches
  use the full volume/lesson/skill/group/question compound key and independent
  question and answer spans.
- Existing preservation and transaction regressions cover approved content,
  manual corrections, progress, attempts, rollback, and retry behavior.
- Learner endpoints never expose an unapproved answer and never grade without
  approved evidence.

## Corrections implemented

1. Added per-exercise interaction configuration through the model, migration,
   API, and learner UI. Multi-blank exercises render separate inputs;
   translation and free response render multiline inputs.
2. Added explicit learner grading states: `graded`, `reference_available`, and
   `pending_review`.
3. Disabled exact-string grading for translation and all automatic grading for
   free response.
4. Fixed duplicate provenance scheduling when SQLAlchemy autoflush is disabled.
5. Recognized the Vietnamese answer-appendix divider even when extracted as a
   header candidate, preventing appendix content from becoming a false lesson.

## Verification

| Check | Result |
|---|---|
| Item-by-item private candidate ledger | 45/45 candidates classified; 3 accepted, 14 need review, 28 withheld |
| Focused parser and acceptance regressions | 14 passed |
| Full API suite | 54 passed, 4 skipped |
| Alembic upgrade -> downgrade -> upgrade | Passed; head `20261026_0012` |
| Frontend unit tests | 2 files, 7 tests passed |
| Next.js production build | Passed |
| Production dependency audit | 0 vulnerabilities |
| Real-PDF private import | 32 unique source pages; one Lesson 01; idempotent re-import |
| Real learner submissions | 5 submitted; 2 graded, 1 reference-only, 2 pending review |
| Browser acceptance | Lesson 01 showed exactly five exercises; a reviewed multiple-choice submission returned the sourced correct result |

PostgreSQL 16 is validated by the task PR's `api-postgres` GitHub Actions job.
The local SQLite acceptance run verifies the private real-PDF path but does not
substitute for PostgreSQL CI.

## Remaining issues

- Fourteen semantically valid original candidates need item-level review before
  publication.
- Four incomplete candidates need parser/grouping repair; they were not silently
  reconstructed or published.
- Image-dependent, table-form, and listening questions remain outside this
  acceptance slice.
- OCR is disabled and Marker remains corroborating evidence only.
- Independent human review remains available and is recommended before merge.
- The branch must not merge until PostgreSQL and web CI checks are green.

## Delivery

- Branch: `codex/task-12-1-lesson01-acceptance`
- Implementation commit: `63bd952e810f63dee4287c1709bb140afb51d1d3`
- Audit-report commit: `629460342a291e307b9ac2e3598589825344619e`
- Draft PR: https://github.com/nhat965/HocTiengHanCung-T/pull/15
- PostgreSQL 16 job: https://github.com/nhat965/HocTiengHanCung-T/actions/runs/40626493246/job/122612535677
- Web test/build job: https://github.com/nhat965/HocTiengHanCung-T/actions/runs/40626493246/job/122612535867
- Both required jobs completed successfully. The PR remains unmerged for review.

