# PDF knowledge schema

`SourceDocument` identifies an owner-scoped private PDF by SHA-256 and records
rights status. `SourcePage`, `SourceBlock`, and `SourceSpan` are the raw
database-backed layer. The structured persistence service associates generated
records with source spans and refuses ambiguous page provenance unless the
source document is specified.

| Layer | Tables | Purpose |
| --- | --- | --- |
| Raw source | `source_documents`, `source_pages`, `source_blocks`, `source_spans` | Page text, text-block coordinates, extracted character spans, OCR candidate flag. |
| Course | `textbooks`, `lessons`, `lesson_sections` | Owner-scoped books, provisional lesson bounds, and section labels. |
| Knowledge | `vocabulary`, `word_senses`, `grammar_patterns`, `sentences`, `sentence_vocabulary`, `sentence_grammar_patterns`, `passages`, `dialogues`, `dialogue_turns` | Structured records, meanings, examples, and relationships. |
| Activities | `exercises`, `exercise_options`, `answer_keys`, `listening_tracks`, `transcripts` | Source-derived activities. Answer keys require their own source span; audio remains `missing` unless a real asset is supplied. |
| Governance | `content_reviews`, `content_provenance`, `import_jobs` | Review state, source/method/version traceability, retries, and job state. |

## Implemented versus pending

The standalone raw JSON exporter includes page dimensions/rotation, text block
and span geometry/font attributes, table candidates and rows, image placement
metadata/assets, source metadata, and source hash. The database worker persists
page text, block geometry, and candidate table rows; it does not persist image
assets, page dimensions, span-level geometry/font metadata, or a raw JSON
archive. The database is not a complete mirror of raw extraction output.

The PDF worker persists the raw layer, runs structured extraction and
validation, then writes structured records, provenance, counts, and quality
summary before the import job enters `needs_review`. Re-import is idempotent
for covered entity keys and does not overwrite approved/reviewed records.
Unique database indexes protect lesson vocabulary/grammar keys, dialogue turns,
exercise options, listening-track identifiers, and provenance. The standalone
structured CLI emits private JSON/quality output but is not the database import
path. No structured knowledge was extracted from the six supplied textbooks.

## Import state machine

`registered → queued → extracting → needs_review`

Each `ImportJob` also tracks a fine-grained stage:
`rights_check`, `raw_extraction`, `raw_persistence`,
`structured_extraction`, `validation`, `structured_persistence`,
`quality_report`, and `complete`. Failures expose `failure_stage`. `failed` and
`needs_review` jobs may be explicitly queued again while
`attempts < max_attempts`. Stale `extracting` jobs are recovered after 60
minutes on the next worker invocation.

`needs_review` means raw and structured source-derived records and a quality
summary have been persisted. It does **not** mean source accuracy has been
reviewed, image assets were stored in the database, or every page was OCR
processed. Records remain `pending`/`unverified` until a human review approves
them. A structured-stage failure rolls back that stage; a previously committed
raw layer remains retryable.

## Private-data boundary

All private document APIs require bearer authentication and filter by the
configured owner. This is a single-owner token model, not multi-user account
management. `rights_status` defaults to `unverified`; raw API/worker extraction
requires a user-declared `authorized` value, not independent legal
verification. Storage isolation does not establish processing or
redistribution rights. Use Alembic for schema changes; startup does not create
or mutate the schema.
