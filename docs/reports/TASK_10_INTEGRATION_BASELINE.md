# Task 10 - Stable Integration Baseline

## Baseline

- Integration branch: `integration/korean-learning-baseline`.
- Selected base: `codex/task-09b-hybrid-extraction` at `a017fa9`.
- Reason: this was the newest green branch containing the complete cumulative
  chain through Task 08.1G, Task 09A, and Task 09B.
- Additional patch-equivalent commits from PR #9:
  - `56ec344` - validate signed private sessions and proxy paths.
  - `7e84013` - add malformed-session and unsafe-path regression tests.
  - `b377c2f` - run frontend regression tests in CI.
- No application feature was designed or added in Task 10. The only repository
  content authored for this task is this integration report; all code changes
  are existing, previously tested commits.

`master` currently ends at `37fe44f` and contains only the merged Task 01 and
Task 02 pull requests. It does not contain the structured knowledge engine,
learning website, Task 08 hardening, Marker pilot, or hybrid extraction work.

## GitHub and dependency audit

All PRs #3-#11 were open and mergeable when audited. None was assumed merged.

| PR | Base -> head | Dependency / content | Included in integration |
|---|---|---|---|
| #3 | `master` -> `codex/task-03-structured-knowledge` | Structured knowledge, worker, initial PostgreSQL pipeline | Yes, ancestor of Task 09B |
| #4 | Task 03 -> `codex/task-04-data-engine` | Review/export/quality engine | Yes, through PR #3 -> #4 |
| #5 | Task 04 -> `codex/task-07-learning-website` | Private website, flashcards and learning progress | Yes, through PR #4 -> #5 |
| #6 | `master` -> `codex/task-08-1c-review-integrity` | Includes Task 08 real-PDF work, 08.1A/B, then review integrity | Yes |
| #7 | `master` -> `codex/task-08-1d-worker-concurrency` | PR #6 plus atomic worker claiming/fencing | Yes |
| #8 | `master` -> `codex/task-08-1e-exercise-extraction` | PR #7 plus exercise/answer linking | Yes |
| #9 | Task 08.1E -> `codex/fix-private-proxy-validation` | Private proxy/session hardening | Yes, cherry-picked once as three patch-equivalent commits |
| #10 | `master` -> `codex/task-08-1g-worker-heartbeat` | PR #8 plus heartbeat/lease renewal; does not contain PR #9 | Yes |
| #11 | `master` -> `codex/task-09b-hybrid-extraction` | PR #10 plus Marker 09A and Hybrid 09B; does not contain PR #9 | Selected base |

Task 08.1A and 08.1B live in the cumulative
`codex/task-08-real-pdf-import` history (`00bc8c1`, `ae991ad`) rather than
separate currently open PRs. Task 08.1C/D/E/G are represented by PRs #6/#7/#8/#10.
The security/proxy work corresponding to the missing branch in that chain is
PR #9. There is no distinct 08.1F migration.

`git cherry` reports the three original PR #9 commits as patch-equivalent to
the three integration commits, proving they were not duplicated semantically.
The integration diff over Task 09B is limited to:

- `.github/workflows/task-03.yml`
- `apps/web/app/api/private/[...path]/route.ts`
- `apps/web/tests/private-session.spec.ts`

No cherry-pick conflict occurred.

## Migration audit

Alembic has one linear head and no duplicate revision:

`20261023_0001 -> 0002 -> 0003 -> 0004 -> 20261024_0005 -> 0006 -> 0007 -> 0008 -> 0009 -> 0010 (head)`

Task 10 did not add or modify a migration. Local in-memory SQLite
`upgrade head -> downgrade base -> upgrade head` passed. PostgreSQL 16 runs the
same cycle in GitHub Actions.

## Operational component inventory

| Component | Status on integration branch |
|---|---|
| PDF Engine | Implemented: page/block/span/table/image extraction with source metadata |
| Marker Hybrid Extraction | Implemented as opt-in sidecar with page mapping, alignment, table recovery and quality checks; not a replacement for the canonical worker path |
| Knowledge Parser | Implemented for lesson segmentation and structured candidates |
| Vocabulary / Grammar / Exercise | Implemented with source references and conservative answer gating |
| Review Workflow | Implemented API, provenance checks, correction history and review page; learner APIs expose approved content only |
| Worker safety | Atomic PostgreSQL claim, skip-locked selection, worker token, heartbeat and lease fencing implemented |
| PostgreSQL persistence | Implemented with one linear migration chain, idempotent keys, transactions and rollback tests |
| Authentication / private proxy | Working private single-owner bearer/session model with HMAC cookie and validated proxy paths; not a general multi-user identity system |
| Flashcards / learning progress | Implemented for vocabulary review, lesson completion, study attempts and grammar notes |
| Regression tests | API, data preservation, review integrity, concurrency, heartbeat, hybrid extraction and private proxy tests retained |

Known non-complete areas remain explicit: OCR uses the safe unresolved adapter
unless a local backend is configured; Marker is an optional sidecar; private
authentication is single-owner; full textbook accuracy has no licensed
independent ground truth.

## Local regression evidence

| Check | Result |
|---|---|
| Full Python API suite | 43 passed, 4 skipped |
| Frontend unit tests | 2 files passed, 7 tests passed |
| Next.js production build | Passed; 8 routes generated/validated |
| Alembic upgrade/downgrade/upgrade | Passed on in-memory SQLite; one head `20261024_0010` |
| npm production dependency audit | 0 vulnerabilities |
| Python requirements audit | No known vulnerabilities |

The API regression suite includes the required preservation and safety cases:

- approved/manual-corrected records and learner progress survive re-import;
- retry and same/different/overlapping page-range imports remain idempotent;
- review approval requires valid source/check evidence;
- learner grading requires an approved answer and complete approved options;
- atomic claims, stale recovery, heartbeat and lease loss are tested;
- owner isolation and private proxy token/session handling are tested.

## Existing green GitHub Actions evidence

| PR | Latest audited green workflow |
|---|---|
| #3 | `40000199602` |
| #4 | `40005691446` |
| #5 | `40073858314` |
| #6 | `40098989808` |
| #7 | `40101747388` |
| #8 | `40109353378` |
| #9 | `40111374012` |
| #10 | `40112507456` |
| #11 | `40191335842` |

Each listed PR check showed successful `api-postgres` and `web-build` jobs at
audit time. The integration PR and its final PostgreSQL 16/frontend CI URL are
recorded below after push.

## Integration PR and final CI

- Integration report commit: pending.
- Integration PR: pending.
- PostgreSQL 16 / frontend CI: pending.

## Remaining issues and merge order

1. Review this single integration PR against `master` and require its
   `api-postgres` and `web-build` jobs to pass.
2. Merge only the integration PR after approval; do not batch-merge PR #3-#11.
3. After the integration merge is verified on `master`, PR #3-#11 can be
   marked superseded/closed in dependency order, preserving links for audit.
4. Do not retarget or close the older PRs before the integration PR is accepted.

The older PRs overlap heavily because later branches contain earlier histories.
Merging them individually would replay already integrated migrations and code,
increase conflict risk, and make the accepted baseline harder to audit.

