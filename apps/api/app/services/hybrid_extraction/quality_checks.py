from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any, Mapping

from app.services.hybrid_extraction.types import (
    AlignmentResult,
    MarkerDocument,
    OcrRegionOutcome,
    TableRecoveryResult,
)
from app.services.knowledge.types import ExtractionBundle


@dataclass(frozen=True)
class HybridQualityReport:
    total_pages_processed: int
    extracted_blocks: int
    aligned_blocks: int
    unresolved_blocks: int
    recovered_table_cells: int
    missing_table_cells: int
    korean_vocabulary_pairs: int
    vietnamese_meanings_recovered: int
    exercise_questions: int
    exercise_options: int
    sourced_answer_keys: int
    ocr_regions_attempted: int
    ocr_regions_unresolved: int
    provenance_coverage: dict[str, int | float]
    status_counts: dict[str, int]
    warnings: list[str]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _record_statuses(bundle: ExtractionBundle) -> dict[str, int]:
    counts: dict[str, int] = {}
    for records in (
        bundle.lessons, bundle.sections, bundle.vocabulary, bundle.grammar,
        bundle.sentences, bundle.dialogue_turns, bundle.passages,
        bundle.exercises, bundle.listening_tracks, bundle.transcripts,
    ):
        for record in records:
            status = str(getattr(record, "validation_status", "unverified"))
            counts[status] = counts.get(status, 0) + 1
            review = str(getattr(record, "review_status", "pending"))
            key = f"review:{review}"
            counts[key] = counts.get(key, 0) + 1
    return counts


def build_quality_report(
    *,
    raw_document: Mapping[str, Any],
    marker: MarkerDocument,
    alignment: AlignmentResult,
    table_recovery: TableRecoveryResult,
    bundle: ExtractionBundle,
    ocr_outcomes: tuple[OcrRegionOutcome, ...] = (),
) -> HybridQualityReport:
    total_pages = len(raw_document.get("pages", []) or [])
    total_blocks = len(marker.blocks)
    aligned = len(alignment.aligned_blocks)
    unresolved_ocr = sum(item.status != "resolved" for item in ocr_outcomes)
    warnings = list(bundle.warnings)
    if alignment.unresolved_blocks:
        warnings.append(f"{len(alignment.unresolved_blocks)} Marker blocks lack a valid raw-span alignment")
    if table_recovery.missing_cells:
        warnings.append(f"{len(table_recovery.missing_cells)} table cells require review")
    return HybridQualityReport(
        total_pages_processed=total_pages,
        extracted_blocks=total_blocks,
        aligned_blocks=aligned,
        unresolved_blocks=len(alignment.unresolved_blocks),
        recovered_table_cells=len(table_recovery.recovered_cells),
        missing_table_cells=len(table_recovery.missing_cells),
        korean_vocabulary_pairs=len(bundle.vocabulary),
        vietnamese_meanings_recovered=sum(len(item.meanings_vi) for item in bundle.vocabulary),
        exercise_questions=sum(1 for item in bundle.exercises if item.prompt and item.parent_id is not None),
        exercise_options=sum(len(item.options) for item in bundle.exercises),
        sourced_answer_keys=sum(
            item.answer is not None and item.answer_source is not None
            for item in bundle.exercises
        ),
        ocr_regions_attempted=len(ocr_outcomes),
        ocr_regions_unresolved=unresolved_ocr,
        provenance_coverage={
            "blocks_total": total_blocks,
            "blocks_aligned": aligned,
            "blocks_unresolved": len(alignment.unresolved_blocks),
            "ratio": round(aligned / total_blocks, 4) if total_blocks else 0.0,
        },
        status_counts=_record_statuses(bundle),
        warnings=warnings,
    )

