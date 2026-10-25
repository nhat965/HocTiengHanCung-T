from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping

from app.services.hybrid_extraction.knowledge_bridge import extract_structured_knowledge
from app.services.hybrid_extraction.layout_alignment import align_marker_blocks
from app.services.hybrid_extraction.marker_adapter import parse_marker_document
from app.services.hybrid_extraction.ocr_fallback import plan_ocr_regions, run_ocr_regions
from app.services.hybrid_extraction.quality_checks import HybridQualityReport, build_quality_report
from app.services.hybrid_extraction.table_recovery import recover_marker_tables
from app.services.hybrid_extraction.types import (
    AlignmentResult,
    MarkerDocument,
    OcrRegionOutcome,
    TableRecoveryResult,
)
from app.services.knowledge.types import ExtractionBundle
from app.services.ocr import OcrAdapter


@dataclass(frozen=True)
class HybridExtractionResult:
    bundle: ExtractionBundle
    marker: MarkerDocument
    alignment: AlignmentResult
    table_recovery: TableRecoveryResult
    ocr_outcomes: tuple[OcrRegionOutcome, ...]
    quality: HybridQualityReport
    enriched_raw: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        return {
            "bundle": self.bundle.to_dict(),
            "quality": self.quality.to_dict(),
            "alignment": {
                "page_mapping": self.alignment.page_mapping,
                "aligned_blocks": len(self.alignment.aligned_blocks),
                "unresolved_blocks": len(self.alignment.unresolved_blocks),
            },
            "table_recovery": {
                "tables": len(self.table_recovery.tables),
                "recovered_cells": len(self.table_recovery.recovered_cells),
                "missing_cells": len(self.table_recovery.missing_cells),
            },
            "ocr": {
                "attempted": len(self.ocr_outcomes),
                "unresolved": sum(item.status != "resolved" for item in self.ocr_outcomes),
            },
        }


def extract_hybrid(
    raw_document: Mapping[str, Any],
    marker_document: Mapping[str, Any] | MarkerDocument | None = None,
    *,
    ocr_adapter: OcrAdapter | None = None,
    run_ocr: bool = False,
) -> HybridExtractionResult:
    """Run Marker alignment and the existing structured parser as one pilot.

    The Marker sidecar is optional and never replaces the raw extraction.  OCR
    outcomes are review signals only; this function intentionally does not
    inject OCR text or approve records.
    """
    if marker_document is None:
        marker = MarkerDocument()
    elif isinstance(marker_document, MarkerDocument):
        marker = marker_document
    else:
        marker = parse_marker_document(marker_document)
    alignment = align_marker_blocks(marker, raw_document)
    table_recovery = recover_marker_tables(marker, raw_document)
    bundle, enriched_raw = extract_structured_knowledge(
        raw_document,
        table_recovery=table_recovery,
    )
    ocr_outcomes: tuple[OcrRegionOutcome, ...] = ()
    if run_ocr:
        requests = plan_ocr_regions(raw_document, marker)
        ocr_outcomes = run_ocr_regions(requests, adapter=ocr_adapter)
        if ocr_outcomes:
            bundle.warnings.append("OCR text remains unresolved/review-only and was not inserted automatically")
    quality = build_quality_report(
        raw_document=raw_document,
        marker=marker,
        alignment=alignment,
        table_recovery=table_recovery,
        bundle=bundle,
        ocr_outcomes=ocr_outcomes,
    )
    return HybridExtractionResult(
        bundle=bundle,
        marker=marker,
        alignment=alignment,
        table_recovery=table_recovery,
        ocr_outcomes=ocr_outcomes,
        quality=quality,
        enriched_raw=enriched_raw,
    )

