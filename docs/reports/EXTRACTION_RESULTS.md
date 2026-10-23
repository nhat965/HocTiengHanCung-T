# Extraction results

Updated 2026-10-23. Counts below are measured from a bounded raw-extraction
pilot, not inferred from plans or synthetic fixtures.

| Volume | Pages processed | Lessons extracted | Vocabulary records | Grammar patterns | Sentences | Reading passages | Dialogues | Exercises | Listening tracks | Transcripts matched | Answers matched | Review required |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|
| 4, lesson 01 only | 18 | 0 structured | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | Yes: all raw page/table/layout output |
| 1, 2, 3, 5, 6 | 0 | Not run | Not run | Not run | Not run | Not run | Not run | Not run | Not run | Not run | Not run | Not assessed |

The volume-4 pilot covers PDF pages 18–35, corresponding to printed pages
17–34. Its local raw JSON is `data/extracted/book-4/lesson-01-raw.json`; the
JSON and extracted images are intentionally not committed because they contain
source textbook content. Aggregate source-file audit measurements are in
[`SOURCE_PDF_AUDIT.md`](./SOURCE_PDF_AUDIT.md).

The pipeline detected 419 text blocks, 3,735 spans, 14 table candidates and 54
images in the pilot range. These are extraction counts only; they are not
verified knowledge records. No OCR, structured vocabulary/grammar extraction,
transcript matching, answer matching, database persistence, or human review
was performed. Therefore this result must not be interpreted as completion of
Task 02 or successful extraction of the six books.
