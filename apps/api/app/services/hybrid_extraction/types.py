from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

BBox = tuple[float, float, float, float]
Point = tuple[float, float]
Polygon = tuple[Point, ...]


@dataclass(frozen=True)
class MarkerBlock:
    """A layout block emitted by Marker.

    ``page_index`` is Marker/JSON's zero-based page index.  ``pdf_page_number``
    is the one-based application value and is always derived as
    ``page_index + 1`` (or from an explicit page mapping supplied by Marker).
    """

    marker_id: str
    block_type: str
    page_index: int
    pdf_page_number: int
    text: str
    html: str | None
    bbox: BBox
    polygon: Polygon
    page_width: float
    page_height: float
    section_hierarchy: tuple[str, ...] = ()

    @property
    def is_table(self) -> bool:
        return self.block_type.casefold() == "table"

    @property
    def is_picture(self) -> bool:
        return self.block_type.casefold() == "picture"


@dataclass(frozen=True)
class MarkerPage:
    page_index: int
    pdf_page_number: int
    width: float
    height: float
    blocks: tuple[MarkerBlock, ...] = ()


@dataclass(frozen=True)
class MarkerDocument:
    pages: tuple[MarkerPage, ...] = ()
    source: dict[str, Any] = field(default_factory=dict)

    @property
    def blocks(self) -> tuple[MarkerBlock, ...]:
        return tuple(block for page in self.pages for block in page.blocks)


@dataclass(frozen=True)
class SourceSpanRef:
    pdf_page_number: int
    span_index: int
    text: str
    bbox: BBox
    block_index: int | None = None


@dataclass(frozen=True)
class AlignedBlock:
    marker: MarkerBlock
    source_spans: tuple[SourceSpanRef, ...] = ()
    status: str = "unresolved"
    overlap_ratio: float = 0.0
    text_similarity: float = 0.0

    @property
    def resolved(self) -> bool:
        return self.status == "aligned" and bool(self.source_spans)


@dataclass(frozen=True)
class AlignmentResult:
    blocks: tuple[AlignedBlock, ...] = ()
    page_mapping: dict[int, int] = field(default_factory=dict)

    @property
    def aligned_blocks(self) -> tuple[AlignedBlock, ...]:
        return tuple(item for item in self.blocks if item.resolved)

    @property
    def unresolved_blocks(self) -> tuple[AlignedBlock, ...]:
        return tuple(item for item in self.blocks if not item.resolved)


@dataclass(frozen=True)
class RecoveredCell:
    page_number: int
    table_index: int
    row_index: int
    column_index: int
    text: str | None
    source_spans: tuple[SourceSpanRef, ...] = ()
    marker_text: str | None = None
    status: str = "needs_review"


@dataclass(frozen=True)
class RecoveredTable:
    page_number: int
    table_index: int
    rows: tuple[tuple[str | None, ...], ...]
    cells: tuple[RecoveredCell, ...]
    status: str = "needs_review"


@dataclass(frozen=True)
class TableRecoveryResult:
    tables: tuple[RecoveredTable, ...] = ()

    @property
    def cells(self) -> tuple[RecoveredCell, ...]:
        return tuple(cell for table in self.tables for cell in table.cells)

    @property
    def recovered_cells(self) -> tuple[RecoveredCell, ...]:
        return tuple(cell for cell in self.cells if cell.status == "recovered")

    @property
    def missing_cells(self) -> tuple[RecoveredCell, ...]:
        return tuple(cell for cell in self.cells if cell.status in {"missing", "needs_review"})


@dataclass(frozen=True)
class OcrRegionRequest:
    pdf_page_number: int
    bbox: BBox
    reason: str
    source_image_index: int | None = None


@dataclass(frozen=True)
class OcrRegionOutcome:
    request: OcrRegionRequest
    status: str
    text: str | None = None
    message: str | None = None

