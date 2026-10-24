from __future__ import annotations

from collections import defaultdict
from pathlib import Path
import re
from typing import Any

from app.services.knowledge.activities import extract_activities
from app.services.knowledge.grammar import extract_grammar
from app.services.knowledge.layout import ordered_blocks, page_tables
from app.services.knowledge.real_layout import extract_real_layout
from app.services.knowledge.segmentation import (
    add_lesson_end_pages,
    detect_lessons,
    detect_sections,
)
from app.services.knowledge.types import ExtractionBundle
from app.services.knowledge.vocabulary import extract_vocabulary

_TOC_MARKER = re.compile(r"(?:목차|차례|mục\s*lục|contents)", re.I)
_APPENDIX_TITLE = re.compile(
    r"^(?:부록(?:\s+\d+)?|정답(?:\s+및\s+해설)?|듣기\s*대본|대본|"
    r"모범\s*답안|answer\s*key|transcripts?)\s*[:：]?$",
    re.I,
)


def extract_knowledge(raw_document: dict[str, Any]) -> ExtractionBundle:
    """Run deterministic, opt-in extractors on a raw-export-shaped document."""
    bundle = ExtractionBundle()
    pages = sorted(raw_document.get("pages", []), key=lambda item: item["pdf_page_number"])
    blocks_by_page = {
        int(page["pdf_page_number"]): ordered_blocks(page)
        for page in pages
    }
    toc_pages = {
        page_number for page_number, blocks in blocks_by_page.items()
        if any(_TOC_MARKER.search(block.text) for block in blocks)
    }
    appendix_start = min(
        (
            page_number
            for page_number, blocks in blocks_by_page.items()
            if any(
                not block.is_header_footer_candidate
                and _APPENDIX_TITLE.fullmatch(" ".join(block.text.split()))
                for block in blocks
            )
        ),
        default=None,
    )
    header_page_occurrences: dict[str, set[int]] = defaultdict(set)
    for page_number, blocks in blocks_by_page.items():
        for block in blocks:
            if block.is_header_footer_candidate:
                header_page_occurrences[" ".join(block.text.casefold().split())].add(page_number)
    repeated_running_text = {
        text for text, page_numbers in header_page_occurrences.items()
        if len(page_numbers) > 1
    }
    all_blocks = []
    content_blocks = []
    content_tables = []
    for page in pages:
        page_number = int(page["pdf_page_number"])
        if page_number in toc_pages:
            continue
        blocks = blocks_by_page[page_number]
        page_blocks = [
            block for block in blocks
            if not (
                block.is_header_footer_candidate
                and " ".join(block.text.casefold().split()) in repeated_running_text
            )
        ]
        all_blocks.extend(page_blocks)
        page_tables_for_extraction = page_tables(page)
        if appendix_start is None or page_number < appendix_start:
            content_blocks.extend(page_blocks)
            content_tables.extend(page_tables_for_extraction)
    declared_page_count = int(
        raw_document.get("source", {}).get("page_count")
        or max((p["pdf_page_number"] for p in pages), default=0)
    )
    processed_page_count = len(pages)
    processed_page_end = max((p["pdf_page_number"] for p in pages), default=0)
    document_page_count = (
        processed_page_end
        if processed_page_count < declared_page_count
        else declared_page_count
    )
    lesson_page_limit = (
        min(document_page_count, appendix_start - 1)
        if appendix_start is not None
        else document_page_count
    )
    bundle.lessons = add_lesson_end_pages(
        detect_lessons(content_blocks),
        lesson_page_limit,
    )
    bundle.sections = detect_sections(content_blocks)
    bundle.vocabulary = extract_vocabulary(content_tables, content_blocks)
    bundle.grammar, bundle.sentences = extract_grammar(content_blocks)
    (
        bundle.dialogue_turns,
        bundle.passages,
        bundle.exercises,
        bundle.listening_tracks,
        bundle.transcripts,
    ) = extract_activities(all_blocks)
    real_dialogues, real_passages, real_exercises = extract_real_layout(content_blocks)
    if not bundle.dialogue_turns:
        bundle.dialogue_turns = real_dialogues
    if not bundle.passages:
        bundle.passages = real_passages
    if not bundle.exercises:
        bundle.exercises = real_exercises
    bundle.warnings.extend(validate_bundle(bundle, {int(page["pdf_page_number"]) for page in pages}))
    if toc_pages:
        bundle.warnings.append(
            "Skipped likely table-of-contents pages: "
            + ", ".join(str(page_number) for page_number in sorted(toc_pages))
        )
    if repeated_running_text:
        bundle.warnings.append(
            f"Filtered {len(repeated_running_text)} repeated header/footer candidates"
        )
    if appendix_start is not None:
        bundle.warnings.append(
            f"Excluded appendix pages from lesson segmentation: {appendix_start}-{document_page_count}"
        )
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
