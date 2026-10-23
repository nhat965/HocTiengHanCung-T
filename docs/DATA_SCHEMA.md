# PDF knowledge schema

`SourceDocument` identifies a registered PDF by SHA-256. `SourcePage`,
`SourceBlock`, and `SourceSpan` are the current database-backed raw layer.
`ContentProvenance` is intended to associate normalized records with source
spans; API write paths do not yet enforce that policy for every entity.

| Layer | Tables | Purpose |
| --- | --- | --- |
| Raw source | `source_documents`, `source_pages`, `source_blocks`, `source_spans` | Page text, text-block coordinates, extracted character spans, OCR candidate flag. |
| Course | `textbooks`, `lessons` | Book and provisional lesson boundaries. |
| Knowledge | `vocabulary`, `word_senses`, `grammar_patterns`, `sentences`, `passages`, `dialogues`, `dialogue_turns` | Reviewed learning material. |
| Activities | `exercises`, `exercise_options`, `answer_keys`, `listening_tracks`, `transcripts` | Source-derived activities. An answer key requires its own source span. |
| Governance | `content_reviews`, `content_provenance`, `import_jobs` | Review decision, traceability, retries, and job state. |

## Implemented versus pending

The standalone JSON exporter currently includes page dimensions/rotation, text
block and span geometry/font attributes, table candidates and rows, image
placement metadata/assets, source metadata, and source hash. The database worker
does **not** yet persist all of these fields: table rows, image assets, page
dimensions, and span-level font/coordinate attributes are pending schema and
worker changes. Do not treat the database as a complete mirror of the raw JSON.

Many-to-many relationships for vocabulary/sentences/grammar and the explicit
exercise group/parent-question relationships are also pending. The tables
currently present are a foundation, not a complete normalized knowledge base.
No structured knowledge was extracted in the measured pilot.

## Import state machine

`registered → queued → extracting → extracted → needs_review → completed`

`failed` may return to `queued` while `attempts < max_attempts`. Re-running a
worker job upserts existing raw pages/blocks and does not delete lessons or
review decisions.

`extracted` means raw source text/block output exists. It does **not** mean
source accuracy has been reviewed, table/image outputs were stored in the
database, or every page was OCR processed.
