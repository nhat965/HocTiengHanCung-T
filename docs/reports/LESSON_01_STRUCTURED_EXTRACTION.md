# Volume 4, Lesson 01 — Structured Extraction Report

## Status

**Not extracted from the textbook.** The source PDFs are private and this task
did not process their contents. Therefore the Bài 01 acceptance criteria are
not met, and no claim is made about the lesson boundary or the accuracy or
completeness of its vocabulary, grammar, reading, exercises, transcript, or
answers.

## Engine verification

The structured extraction code was exercised with a two-page synthetic fixture
containing Korean and Vietnamese examples and a two-column vocabulary table.
The fixture produced:

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

## Limitations

- These counts are synthetic test results, not records extracted from the
  textbook.
- The rules are deterministic and marker/layout dependent; they require human
  review and have not been benchmarked against the supplied PDFs.
- Structured JSON generation and quality reporting are available through the
  private CLI. Automated structured ingestion from the PDF worker into
  PostgreSQL is not yet wired.
- PostgreSQL migration behavior and real-source visual verification are
  outstanding. The migration was checked on temporary SQLite only.
- No copyrighted source text, PDF, or extraction output is included in this
  report or intended for Git.
