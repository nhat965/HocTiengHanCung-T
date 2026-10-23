from __future__ import annotations

from pathlib import Path
from typing import Any

from app.services.knowledge.activities import extract_activities
from app.services.knowledge.grammar import extract_grammar
from app.services.knowledge.layout import ordered_blocks, page_tables
from app.services.knowledge.segmentation import (
    add_lesson_end_pages,
    detect_lessons,
    detect_sections,
)
from app.services.knowledge.types import ExtractionBundle
from app.services.knowledge.vocabulary import extract_vocabulary


def extract_knowledge(raw_document: dict[str, Any]) -> ExtractionBundle:
    """Run deterministic, opt-in extractors on a raw-export-shaped document."""
    bundle = ExtractionBundle()
    pages = sorted(raw_document.get("pages", []), key=lambda item: item["pdf_page_number"])
    all_blocks = []
    tables = []
    for page in pages:
        all_blocks.extend(ordered_blocks(page))
        tables.extend(page_tables(page))
    bundle.lessons = add_lesson_end_pages(
        detect_lessons(all_blocks),
        int(raw_document.get("source", {}).get("page_count") or max((p["pdf_page_number"] for p in pages), default=0)),
    )
    bundle.sections = detect_sections(all_blocks)
    bundle.vocabulary = extract_vocabulary(tables)
    bundle.grammar, bundle.sentences = extract_grammar(all_blocks)
    (
        bundle.dialogue_turns,
        bundle.passages,
        bundle.exercises,
        bundle.listening_tracks,
        bundle.transcripts,
    ) = extract_activities(all_blocks)
    bundle.warnings.extend(validate_bundle(bundle, {int(page["pdf_page_number"]) for page in pages}))
    return bundle


def validate_bundle(bundle: ExtractionBundle, available_pages: set[int]) -> list[str]:
    warnings: list[str] = []
    records = (
        bundle.lessons + bundle.sections + bundle.vocabulary + bundle.grammar
        + bundle.sentences + bundle.dialogue_turns + bundle.passages
        + bundle.exercises + bundle.listening_tracks + bundle.transcripts
    )
    for record in records:
        if record.source.pdf_page_number not in available_pages:
            warnings.append(f"Missing source page {record.source.pdf_page_number}")
    patterns: set[str] = set()
    for grammar in bundle.grammar:
        if grammar.normalized_pattern in patterns:
            warnings.append(f"Duplicate grammar pattern needs review on page {grammar.source.pdf_page_number}")
        patterns.add(grammar.normalized_pattern)
    tracks_with_transcript = {item.track_identifier for item in bundle.transcripts}
    for track in bundle.listening_tracks:
        normalized = "".join(char for char in track.track_identifier.upper() if char.isalnum())
        if normalized not in { "".join(char for char in item.upper() if char.isalnum()) for item in tracks_with_transcript }:
            warnings.append(f"Transcript not found for track {track.track_identifier}")
    for exercise in bundle.exercises:
        if exercise.parent_id is None and exercise.answer is None:
            warnings.append(f"Answer not found for exercise {exercise.local_id}")
    return warnings


def write_knowledge_json(bundle: ExtractionBundle, output_path: Path, source_metadata: dict[str, Any]) -> Path:
    import json
    from datetime import datetime, timezone

    output_path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "schema_version": bundle.schema_version,
        "extraction_version": bundle.extraction_version,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "validation_status": "review_required" if bundle.warnings else "unverified",
        "source": {
            "filename": source_metadata.get("filename"),
            "sha256": source_metadata.get("sha256"),
            "page_count": source_metadata.get("page_count"),
        },
        "data": bundle.to_dict(),
    }
    output_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return output_path
