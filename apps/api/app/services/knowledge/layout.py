from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class SourceBlock:
    page_number: int
    printed_page_number: str | None
    block_index: int
    text: str
    bbox: tuple[float, float, float, float]
    page_width: float
    page_height: float
    is_header_footer_candidate: bool


@dataclass(frozen=True)
class SourceTable:
    page_number: int
    printed_page_number: str | None
    table_index: int
    bbox: tuple[float, float, float, float]
    rows: list[list[str | None]]


def ordered_blocks(page: dict[str, Any]) -> list[SourceBlock]:
    """Order page blocks by layout regions, not PyMuPDF's input list order."""
    width = float(page.get("width") or 0)
    blocks = [
        SourceBlock(
            page_number=int(page["pdf_page_number"]),
            printed_page_number=page.get("printed_page_number"),
            block_index=int(block["index"]),
            text=str(block.get("text") or "").strip(),
            bbox=tuple(float(value) for value in block["bbox"]),
            page_width=width,
            page_height=float(page.get("height") or 0),
            is_header_footer_candidate=bool(block.get("is_header_footer_candidate", False)),
        )
        for block in page.get("blocks", [])
        if str(block.get("text") or "").strip()
    ]
    if not blocks:
        return []
    centers = [((block.bbox[0] + block.bbox[2]) / 2) / width for block in blocks if width]
    has_columns = (
        len(centers) >= 4
        and any(center < 0.45 for center in centers)
        and any(center > 0.55 for center in centers)
    )
    if not has_columns:
        return sorted(blocks, key=lambda block: (round(block.bbox[1], 1), block.bbox[0]))

    spanning = sorted(
        (
            block for block in blocks
            if width and block.bbox[2] - block.bbox[0] >= width * 0.68
        ),
        key=lambda block: block.bbox[1],
    )
    ordered: list[SourceBlock] = []
    previous_anchor_y = float("-inf")

    def append_column_band(band: list[SourceBlock]) -> None:
        for column in (0, 1):
            column_blocks = [
                block for block in band
                if ((block.bbox[0] + block.bbox[2]) / 2 < width / 2) == (column == 0)
            ]
            ordered.extend(sorted(
                column_blocks,
                key=lambda block: (round(block.bbox[1], 1), block.bbox[0]),
            ))

    for anchor in spanning:
        anchor_y = (anchor.bbox[1] + anchor.bbox[3]) / 2
        band = [
            block for block in blocks
            if block not in spanning
            and previous_anchor_y < (block.bbox[1] + block.bbox[3]) / 2 < anchor_y
        ]
        append_column_band(band)
        ordered.append(anchor)
        previous_anchor_y = anchor_y
    append_column_band([
        block for block in blocks
        if block not in spanning
        and (block.bbox[1] + block.bbox[3]) / 2 > previous_anchor_y
    ])
    return ordered


def page_tables(page: dict[str, Any]) -> list[SourceTable]:
    return [
        SourceTable(
            page_number=int(page["pdf_page_number"]),
            printed_page_number=page.get("printed_page_number"),
            table_index=int(table["index"]),
            bbox=tuple(float(value) for value in table.get("bbox", (0, 0, 0, 0))),
            rows=[[None if cell is None else str(cell).strip() for cell in row] for row in table.get("rows", [])],
        )
        for table in page.get("tables", [])
    ]
