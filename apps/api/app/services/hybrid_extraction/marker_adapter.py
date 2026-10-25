from __future__ import annotations

from html.parser import HTMLParser
import json
import re
from pathlib import Path
from typing import Any, Mapping

from app.services.hybrid_extraction.types import (
    BBox,
    MarkerBlock,
    MarkerDocument,
    MarkerPage,
    Point,
    Polygon,
)


class _HtmlTextParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.parts: list[str] = []

    def handle_data(self, data: str) -> None:
        self.parts.append(data)


_PAGE_INDEX = re.compile(r"/page/(\d+)(?:/|$)", re.I)


def html_to_text(value: str | None) -> str:
    """Convert Marker HTML to reviewable text without inventing content."""
    if not value:
        return ""
    parser = _HtmlTextParser()
    parser.feed(value)
    parser.close()
    return " ".join("".join(parser.parts).split())


def _bbox(value: Any) -> BBox:
    if isinstance(value, (list, tuple)) and len(value) >= 4:
        return tuple(float(item) for item in value[:4])  # type: ignore[return-value]
    return (0.0, 0.0, 0.0, 0.0)


def _polygon(value: Any, bbox: BBox) -> Polygon:
    points: list[Point] = []
    if isinstance(value, (list, tuple)):
        for point in value:
            if isinstance(point, (list, tuple)) and len(point) >= 2:
                points.append((float(point[0]), float(point[1])))
    if points:
        return tuple(points)
    x0, y0, x1, y1 = bbox
    return ((x0, y0), (x1, y0), (x1, y1), (x0, y1))


def _page_index(node: Mapping[str, Any], fallback: int) -> int:
    marker_id = str(node.get("id") or "")
    match = _PAGE_INDEX.search(marker_id)
    return int(match.group(1)) if match else fallback


def _page_size(node: Mapping[str, Any]) -> tuple[float, float]:
    bbox = _bbox(node.get("bbox"))
    polygon = _polygon(node.get("polygon"), bbox)
    max_x = max((point[0] for point in polygon), default=bbox[2])
    max_y = max((point[1] for point in polygon), default=bbox[3])
    return (max(float(max_x), float(bbox[2]), 1.0), max(float(max_y), float(bbox[3]), 1.0))


def _flatten_blocks(
    node: Mapping[str, Any],
    *,
    page_index: int,
    pdf_page_number: int,
    page_width: float,
    page_height: float,
    section_hierarchy: tuple[str, ...] = (),
) -> list[MarkerBlock]:
    blocks: list[MarkerBlock] = []
    block_type = str(node.get("block_type") or "").strip() or "Unknown"
    if block_type.casefold() != "page":
        bbox = _bbox(node.get("bbox"))
        html = node.get("html") if isinstance(node.get("html"), str) else None
        raw_text = node.get("text") if isinstance(node.get("text"), str) else None
        text = " ".join((raw_text if raw_text is not None else html_to_text(html)).split())
        hierarchy = node.get("section_hierarchy")
        if isinstance(hierarchy, list):
            effective_hierarchy = tuple(str(item) for item in hierarchy if str(item).strip())
        else:
            effective_hierarchy = section_hierarchy
        blocks.append(MarkerBlock(
            marker_id=str(node.get("id") or f"/page/{page_index}/{len(blocks)}"),
            block_type=block_type,
            page_index=page_index,
            pdf_page_number=pdf_page_number,
            text=text,
            html=html,
            bbox=bbox,
            polygon=_polygon(node.get("polygon"), bbox),
            page_width=page_width,
            page_height=page_height,
            section_hierarchy=effective_hierarchy,
        ))
    for child in node.get("children") or ():
        if isinstance(child, Mapping):
            blocks.extend(_flatten_blocks(
                child,
                page_index=page_index,
                pdf_page_number=pdf_page_number,
                page_width=page_width,
                page_height=page_height,
                section_hierarchy=section_hierarchy,
            ))
    return blocks


def parse_marker_document(document: Mapping[str, Any]) -> MarkerDocument:
    """Parse Marker JSON into the internal, one-based layout schema.

    The conversion is deliberately lossless for source references: original
    Marker IDs, HTML, polygons, and zero-based page indexes remain available.
    """
    pages: list[MarkerPage] = []
    roots = document.get("children") or []
    for fallback, node in enumerate(roots):
        if not isinstance(node, Mapping):
            continue
        if str(node.get("block_type") or "").casefold() != "page":
            continue
        page_index = _page_index(node, fallback)
        page_width, page_height = _page_size(node)
        page_number = page_index + 1
        page_blocks = _flatten_blocks(
            node,
            page_index=page_index,
            pdf_page_number=page_number,
            page_width=page_width,
            page_height=page_height,
        )
        pages.append(MarkerPage(
            page_index=page_index,
            pdf_page_number=page_number,
            width=page_width,
            height=page_height,
            blocks=tuple(page_blocks),
        ))
    pages.sort(key=lambda item: item.page_index)
    return MarkerDocument(pages=tuple(pages), source=dict(document.get("metadata") or {}))


def load_marker_json(path: Path) -> MarkerDocument:
    with path.open("r", encoding="utf-8") as handle:
        value = json.load(handle)
    if not isinstance(value, Mapping):
        raise ValueError("Marker JSON root must be an object")
    return parse_marker_document(value)

