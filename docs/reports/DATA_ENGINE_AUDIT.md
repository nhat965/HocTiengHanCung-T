# Task 04 data-engine audit

Audit date: 2026-10-24

## Repository state at audit

- Main integration work exists in open PR #3, `codex/task-03-structured-knowledge`
  → `master`: <https://github.com/nhat965/HocTiengHanCung-T/pull/3>.
- Audited Task 03 head: `a283eb6`; GitHub reported the PR mergeable and both
  `api-postgres` and `web-build` successful.
- Task 04 work is isolated on `codex/task-04-data-engine` and builds on PR #3.
- Baseline local suite before Task 04: 19 passing tests.

## Source inventory and rights boundary

Six textbook PDFs are physically present under local `docs/`, but are untracked
and were not found in Git history. They are source PDFs only—not raw JSON,
structured JSON, database records, generated content, or reviewed content.
No processing/reuse authorization was supplied, so Task 04 does not create or
publish a corpus from them. `.gitignore` explicitly excludes `docs/*.pdf`.

## Implemented before Task 04

- Raw PDF extraction: page text, blocks, spans, fonts, bounding boxes, tables,
  images, PDF/printed page numbers, metadata, Unicode/NUL safety and private JSON.
- Structured extraction modules and generated fixtures for lesson boundaries,
  Korean–Vietnamese vocabulary tables, grammar/examples, dialogue, reading,
  exercise/options/source answer, listening track and transcript.
- PostgreSQL-oriented relational schema, Alembic migrations, owner-scoped private
  storage, rights gate, staged worker/retry/recovery, idempotent persistence,
  exact provenance, approved-record preservation, deletion and read APIs.
- PostgreSQL 16 CI, migration round-trip, dependency audits and frontend build.

## Gaps identified at audit

- OCR was a boolean requirement flag, not an adapter contract.
- Normalization was split across extractors and used compatibility normalization
  for source-language keys without a single conservative policy.
- Sentence identity and source occurrence were not separated.
- Review history existed as a table but had no usable list/update API.
- Dialogue retrieval and dataset exports were missing.
- Persisted quality reporting was too shallow for required type/lesson metrics.
- No current task branch was included in CI triggers.

## Data-layer distinctions

- **Source PDF:** private input bytes; never returned by an API.
- **Raw extraction:** source-faithful page/block/span/table/image metadata.
- **Structured extraction:** deterministic candidate records, initially pending.
- **Database record:** persisted candidate plus relationship and provenance.
- **Generated content:** not produced by this task.
- **Reviewed content:** a human decision recorded separately; only `approved` is
  selected by default for exports.
