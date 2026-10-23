# Data Quality Report

## Scope and status

No structured extraction was run on the six private textbook PDFs. Accuracy
against those sources is **not measured**. The values below describe only the
synthetic fixture in `test_knowledge_extractors.py`.

## Structured extractor fixture coverage

| Measure | Result |
| --- | ---: |
| Fixture pages processed / total | 2 / 2 |
| Lessons / sections | 1 / 1 |
| Vocabulary / entries without meanings | 2 / 0 |
| Grammar patterns / patterns without examples | 1 / 0 |
| Example sentences | 1 |
| Dialogue turns | 2 |
| Reading passages / ordered paragraphs | 1 / 2 |
| Exercise groups and questions / options | 2 / 2 |
| Questions with sourced answers | 1 / 1 |
| Listening tracks / matched transcripts | 1 / 1 |
| Structured records with source page references | All fixture records |
| Approved records overwritten by re-import | 0 |

The fixture checks table-row source references, track/transcript normalization,
answer-key source linkage, and reading paragraph order. A second fixture checks
that TOC entries and blocks marked as running headers are not detected as
lesson starts.

## End-to-end generated-PDF worker coverage

The worker test creates a one-page PDF at test time with PyMuPDF, extracts it,
persists the extracted records to the test database, and retrieves them through
the authenticated API. It contains no textbook material.

| Measure | Result |
| --- | ---: |
| Generated PDF pages processed / total | 1 / 1 |
| Lessons / vocabulary entries | 1 / 2 |
| Grammar patterns / linked example sentences | 1 / 1 |
| Reading passages / paragraphs | 1 / 2 |
| Exercise questions / options / sourced answers | 1 / 2 / 1 |
| Listening tracks / matched transcripts | 1 / 1 |
| Source-page references on persisted records | Present |
| Records returned by API after persistence | Verified |
| Duplicate structured records after retry | 0 |
| Approved records overwritten during re-import | 0 |
| Structured records left after forced mid-stage failure | 0 |
| Orphaned source-derived rows after document deletion | 0 |

Dialogue turns are covered by the two-page structured fixture above, not by
the generated-PDF worker fixture. This is functional test coverage, not a
measurement of extractor precision or recall.

## Quality interpretation

- **Coverage** counts the pages made available to the extractor; it does not
  measure extraction accuracy.
- **Accuracy** requires comparison against the source and human review. It is
  unmeasured for both the six textbooks and the synthetic fixtures.
- Unmatched answers or transcripts remain missing and are not inferred.
- Page-level provenance is retained; ambiguous page references across multiple
  source PDFs fail unless the caller specifies the source document.
- No confidence or 100% accuracy claim is made.

## Outstanding checks

- Run a permitted, visually reviewed real-document pilot before accepting
  textbook-specific extraction quality.
- Verify migrations and the worker integration suite on a live PostgreSQL
  instance through CI; local PostgreSQL was unavailable.
- Build a review workflow that records reviewer decisions and adjudicates
  uncertain layout/table extraction.
