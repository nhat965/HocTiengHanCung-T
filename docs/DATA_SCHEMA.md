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

Structured extraction can write fixture-derived records through the persistence
service. Re-import is idempotent for tested entity keys and does not overwrite
approved/reviewed rows. The structured CLI currently emits JSON/quality output;
it is not connected to an automatic PDF-worker or API ingestion stage. No
structured knowledge was extracted from the six supplied textbooks.

## Import state machine

`registered → queued → extracting → extracted → needs_review → completed`

`failed` may return to `queued` while `attempts < max_attempts`. Re-running a
worker job upserts existing raw pages/blocks and does not delete lessons or
review decisions.

`extracted` means raw source text/block output exists. It does **not** mean
source accuracy has been reviewed, table/image outputs were stored in the
database, or every page was OCR processed. Structured fixture records are
`pending`/`unverified` until a human review approves them.

## Private-data boundary

All private document APIs require bearer authentication and filter by the
configured owner. This is a single-owner token model, not multi-user account
management. `rights_status` defaults to `unverified`; raw API/worker extraction requires a
user-declared `authorized` value, not independent legal verification.
Storage isolation does not establish processing or redistribution rights. Use Alembic for schema
changes; startup does not create or mutate the schema.
