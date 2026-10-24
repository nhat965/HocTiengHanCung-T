# Task 08 — real PDF import pilot

## Result at a glance

The real-source pilot was executed locally against the private copy of
`[Tailieuvui.com]_giao-trinh-tieng-han-tong-hop-trung-cap-4-pdf.pdf`. The
bounded range is PDF pages **18–35** (18 pages), which maps to printed pages
17–34 and contains **Bài 01 — 유행**. The extraction worker completed and the
result was read back through the owner-scoped API and the learning website.

This is a **private SQLite acceptance run**, not a PostgreSQL acceptance run:
there is no PostgreSQL server or Docker runtime available in this workspace.
The repository's PostgreSQL migration/integration path remains covered by the
existing CI run referenced below; this report does not claim that the local
pilot was persisted to PostgreSQL.

## Source and rights boundary

- Source: local file under `docs/`; the six local PDFs are inventoried in
  [`SOURCE_PDF_AUDIT.md`](SOURCE_PDF_AUDIT.md).
- Rights scope: the user confirmed local, personal-only processing for this
  pilot on **2026-10-24**. No source PDF, raw extraction JSON, image asset, or
  textbook passage is committed to Git.
- The remaining five books were not imported. Their metadata audit is retained,
  but no permission to redistribute or publish their contents is inferred.

## Pilot extraction and persisted counts

| Entity | Count | Review/quality interpretation |
|---|---:|---|
| PDF pages processed | 18 | PDF 18–35; printed 17–34 |
| Lessons | 1 | Bài 01 — 유행 |
| Lesson sections | 12 | source-backed section spans |
| Vocabulary | 59 | 59 word senses persisted; 10 manually reviewed/approved |
| Grammar patterns | 3 | all 3 manually reviewed/approved |
| Example sentences | 24 | source spans retained; learner API exposes approved examples |
| Dialogue groups / turns | 7 / 25 | order and source spans retained |
| Reading passages | 4 | source spans retained |
| Exercises | 67 | 3 manually reviewed/approved for the learner UI |
| Exercise options | 0 | no options were invented |
| Listening tracks | 5 | metadata only |
| Transcripts / answer keys | 0 / 0 | unresolved source classes; not fabricated |
| Explicit unresolved source markers | 0 | no unresolved marker row was emitted by this run |

The extraction job ended in `needs_review` with stage `complete`, one attempt,
and a retry budget of three. Remaining candidates stay pending and are not
shown in the learner tabs. Approval calls required source span, expected
version, reviewer action, and structural/semantic checks; no bulk auto-approve
was used.

## Quality review

The review sample was compared with rendered pages from the local PDF before
approval:

- 10 vocabulary records (including their word senses);
- 3 grammar patterns; and
- 3 exercise prompts.

The review verified Korean text, Vietnamese meaning where present, page/span
provenance, ordering, and lesson membership. No answer was inferred when the
source did not provide one. The pilot still needs a larger manually labelled
ground-truth set before full-book import; layout-heavy tables, transcript
matching, and OCR are not validated by this pilot.

## API and website acceptance

The private API was exercised with the owner bearer token and returned the
single imported book and lesson. The browser journey on `http://localhost:3000`
completed:

1. login to the private session;
2. open Trung cấp 4 → Bài 01 — 유행;
3. view the overview (10 approved vocabulary, 3 approved grammar patterns,
   2 approved learner exercises);
4. open the vocabulary flashcard and save a learned state;
5. submit an exercise response and receive the pending-answer state; and
6. reload the lesson after closing duplicate browser tabs, with the lesson and
   saved progress still available.

The API re-import was idempotent: the second registration returned
`already_imported=true` and reused the existing job/document instead of
creating duplicates. The job remained `needs_review`.

## Automated verification

- API suite: 27 tests passed locally on SQLite after the pilot database
  connection was configured with a busy timeout and WAL mode.
- Web production build: passed (`npm run build:web`).
- Task 08 branch CI: migration upgrade/downgrade, PostgreSQL API integration,
  dependency audit, and web build all passed in run
  [40076450656](https://github.com/nhat965/HocTiengHanCung-T/actions/runs/40076450656)
  at commit `6dbdabeeb84d9d104122a0f60a68cd698b6ade02`. This is hosted CI
  evidence, not a local PostgreSQL service.
- The private pilot database and evidence JSON remain under the Git-ignored
  `private-data/pilot-a/` directory.

## Blockers and next gate

1. **PostgreSQL local proof is blocked** until a PostgreSQL service (or an
   approved CI/remote database) is available. The SQLite run must not be
   presented as satisfying the PostgreSQL requirement.
2. OCR is not enabled in this environment. Image-only regions must remain
   unresolved until a Korean/Vietnamese OCR adapter and quality threshold are
   configured.
3. Transcript/answer-key matching is unresolved for this page range.
4. The other five books and the remainder of volume 4 are intentionally not
   imported until this pilot's review and rights boundary are accepted.

The next safe gate is to repeat this exact job against PostgreSQL, compare the
same approved sample, and attach a PostgreSQL evidence record before expanding
the import range.

## Git handoff

- Pilot implementation/report commit: `9bf33143869a326f0460ba407d69de5747dbd4f8`.
- CI trigger commit: `6dbdabeeb84d9d104122a0f60a68cd698b6ade02`.
- Branch: `codex/task-08-real-pdf-import`.
