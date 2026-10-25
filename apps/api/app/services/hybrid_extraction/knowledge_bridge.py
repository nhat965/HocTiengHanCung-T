from __future__ import annotations

from typing import Any, Mapping

from app.services.knowledge.pipeline import extract_knowledge
from app.services.knowledge.types import ExtractionBundle
from app.services.hybrid_extraction.table_recovery import apply_table_recovery
from app.services.hybrid_extraction.types import TableRecoveryResult


def extract_structured_knowledge(
    raw_document: Mapping[str, Any],
    *,
    table_recovery: TableRecoveryResult | None = None,
) -> tuple[ExtractionBundle, dict[str, Any]]:
    """Feed recovered evidence into the existing deterministic knowledge engine.

    This is intentionally a bridge, not a second vocabulary/grammar/exercise
    parser.  Existing parser rules, review defaults, and persistence contracts
    remain authoritative.
    """
    enriched = (
        apply_table_recovery(raw_document, table_recovery)
        if table_recovery is not None
        else dict(raw_document)
    )
    return extract_knowledge(enriched), enriched

