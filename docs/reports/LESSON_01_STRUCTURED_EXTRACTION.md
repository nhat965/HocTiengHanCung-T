# Volume 4, Lesson 01 — Structured Extraction Report

## Status

**Not extracted from the textbook.** The source PDFs are private and this task
did not process their contents. Therefore the Bài 01 acceptance criteria are
not met, and no claim is made about the lesson boundary or the accuracy or
completeness of its vocabulary, grammar, reading, exercises, transcript, or
answers.

## Engine verification

No textbook extraction is claimed. Engine behavior is checked using two
permitted synthetic test inputs. The first is a two-page structured-data
fixture with Korean and Vietnamese examples and a two-column vocabulary table:

| Record | Count |
| --- | ---: |
| Lesson / section | 1 / 1 |
| Vocabulary entries | 2 |
| Grammar patterns / linked example sentences | 1 / 1 |
| Dialogue turns | 2 |
| Reading passages / ordered paragraphs | 1 / 2 |
| Exercise group and question / options | 2 / 2 |
| Sourced answer keys | 1 |
| Listening tracks / matched transcripts | 1 / 1 |

Every generated fixture record includes a source page reference. Vocabulary
records point to source table rows. Re-import keeps the approved vocabulary
record unchanged; a separate case checks that duplicate PDF page numbers do
not silently attach provenance to the wrong source document.

The end-to-end worker integration test also generates a one-page PDF in the
test process and verifies extraction, validation, database persistence, and
API retrieval. It produces 1 lesson, 2 vocabulary entries, 1 grammar pattern
with 1 linked example sentence, 1 reading passage with 2 ordered paragraphs,
1 exercise question with 2 options and 1 sourced answer, and 1 listening track
with 1 matched transcript. Every persisted structured record has source-page
provenance. Re-import produces no duplicates and leaves approved records
unchanged; forced structured-stage failure rolls back derived records.

API test execution covered rights checks, owner scoping, document deletion,
stale-job recovery, multi-column reading order, and TOC/header filtering.

## Limitations

- All counts are synthetic test results, not records extracted from the
  textbook.
- The rules are deterministic and marker/layout dependent; they require human
  review and have not been benchmarked against the supplied PDFs.
- The PDF worker now integrates structured extraction, validation, database
  persistence, provenance, and quality reporting. Local end-to-end validation
  used SQLite; PostgreSQL CI execution is pending.
- Real-source visual verification is outstanding.
- No copyrighted source text, PDF, or extraction output is included in this
  report or intended for Git.
