from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import SourceBlock, SourcePage, SourceSpan
from app.services.hybrid_extraction.types import AlignmentResult, SourceSpanRef


@dataclass(frozen=True)
class PersistedSourceRef:
    source_page_id: int
    source_block_id: int | None
    source_span_id: int


@dataclass(frozen=True)
class ProvenanceAlignment:
    marker_id: str
    source_refs: tuple[PersistedSourceRef, ...]
    status: str


def _resolve_span(
    session: Session,
    source_document_id: int,
    source: SourceSpanRef,
) -> PersistedSourceRef | None:
    page = session.scalar(select(SourcePage).where(
        SourcePage.source_document_id == source_document_id,
        SourcePage.pdf_page_number == source.pdf_page_number,
    ))
    if page is None:
        return None
    query = (
        select(SourceSpan, SourceBlock)
        .join(SourceBlock, SourceSpan.source_block_id == SourceBlock.id, isouter=True)
        .where(SourceSpan.source_page_id == page.id)
    )
    if source.block_index is not None:
        query = query.where(SourceBlock.block_index == source.block_index)
    else:
        query = query.where(SourceSpan.raw_text == source.text)
    rows = session.execute(query).all()
    # Ambiguous matches are deliberately unresolved.  Picking the first row
    # would silently attach a Marker block to the wrong source span.
    if len(rows) != 1:
        return None
    span, block = rows[0]
    return PersistedSourceRef(
        source_page_id=page.id,
        source_block_id=block.id if block is not None else None,
        source_span_id=span.id,
    )


def resolve_persisted_provenance(
    session: Session,
    source_document_id: int,
    alignment: AlignmentResult,
) -> tuple[ProvenanceAlignment, ...]:
    """Resolve aligned raw references to persisted IDs without fabricating IDs."""
    output: list[ProvenanceAlignment] = []
    for aligned in alignment.blocks:
        resolved = tuple(
            item for item in (
                _resolve_span(session, source_document_id, source)
                for source in aligned.source_spans
            )
            if item is not None
        )
        output.append(ProvenanceAlignment(
            marker_id=aligned.marker.marker_id,
            source_refs=resolved,
            status="aligned" if resolved and len(resolved) == len(aligned.source_spans) else "unresolved",
        ))
    return tuple(output)

