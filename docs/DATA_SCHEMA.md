# PDF knowledge schema

`SourceDocument` is the immutable registered PDF reference. `SourcePage`, `SourceBlock`, and `SourceSpan` preserve the raw, per-page extraction trail. No structured learning record may be presented as textbook content without a `ContentProvenance` reference to a source span.

| Layer | Tables | Purpose |
| --- | --- | --- |
| Raw source | `source_documents`, `source_pages`, `source_blocks`, `source_spans` | Exact PDF page, layout coordinates, normalized span text, OCR flag. |
| Course | `textbooks`, `lessons` | Book and provisional lesson boundaries. |
| Knowledge | `vocabulary`, `word_senses`, `grammar_patterns`, `sentences`, `passages`, `dialogues`, `dialogue_turns` | Reviewed learning material. |
| Activities | `exercises`, `exercise_options`, `answer_keys`, `listening_tracks`, `transcripts` | Source-derived activities. An answer key requires its own source span. |
| Governance | `content_reviews`, `content_provenance`, `import_jobs` | Review decision, traceability, retries, and job state. |

## Import state machine

`registered → queued → extracting → extracted → needs_review → completed`

`failed` may return to `queued` while `attempts < max_attempts`. Registration never asserts review is needed before an extraction has actually generated reviewable output.

`extracted` means raw source output exists. It does **not** mean source accuracy has been reviewed or that every page was OCR processed.
