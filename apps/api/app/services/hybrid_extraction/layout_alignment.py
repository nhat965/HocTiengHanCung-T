from __future__ import annotations

from difflib import SequenceMatcher
import re
from typing import Any, Mapping

from app.services.hybrid_extraction.types import (
    AlignedBlock,
    AlignmentResult,
    BBox,
    MarkerDocument,
    MarkerPage,
    MarkerBlock,
    SourceSpanRef,
)

_SPACE = re.compile(r"\s+")
_NON_WORD = re.compile(r"[^\w\uac00-\ud7a3À-ỹ]+", re.UNICODE)


def normalize_source_text(value: str) -> str:
    return _SPACE.sub(" ", _NON_WORD.sub(" ", value.casefold())).strip()


def bbox_from_polygon(polygon: tuple[tuple[float, float], ...]) -> BBox:
    if not polygon:
        return (0.0, 0.0, 0.0, 0.0)
    xs = [point[0] for point in polygon]
    ys = [point[1] for point in polygon]
    return min(xs), min(ys), max(xs), max(ys)


def scale_bbox(bbox: BBox, *, from_width: float, from_height: float, to_width: float, to_height: float) -> BBox:
    x_scale = to_width / from_width if from_width else 1.0
    y_scale = to_height / from_height if from_height else 1.0
    return (bbox[0] * x_scale, bbox[1] * y_scale, bbox[2] * x_scale, bbox[3] * y_scale)


def intersection_area(left: BBox, right: BBox) -> float:
    width = max(0.0, min(left[2], right[2]) - max(left[0], right[0]))
    height = max(0.0, min(left[3], right[3]) - max(left[1], right[1]))
    return width * height


def overlap_ratio(left: BBox, right: BBox) -> float:
    area = max(0.0, left[2] - left[0]) * max(0.0, left[3] - left[1])
    return intersection_area(left, right) / area if area else 0.0


def _center(bbox: BBox) -> tuple[float, float]:
    return ((bbox[0] + bbox[2]) / 2.0, (bbox[1] + bbox[3]) / 2.0)


def _contains(outer: BBox, inner: BBox) -> bool:
    x, y = _center(inner)
    return outer[0] <= x <= outer[2] and outer[1] <= y <= outer[3]


def _text_similarity(left: str, right: str) -> float:
    a = normalize_source_text(left)
    b = normalize_source_text(right)
    if not a or not b:
        return 0.0
    if a in b or b in a:
        return 1.0
    return SequenceMatcher(None, a, b, autojunk=False).ratio()


def _page_index_map(marker: MarkerDocument, raw_document: Mapping[str, Any]) -> dict[int, int]:
    raw_pages = {int(page.get("pdf_page_number")): page for page in raw_document.get("pages", [])}
    mapping: dict[int, int] = {}
    for page in marker.pages:
        candidate = page.page_index + 1
        if candidate in raw_pages:
            mapping[page.page_index] = candidate
            continue
        # A bounded import can start at a non-zero PDF page while Marker still
        # numbers its first emitted page from the source document.  Match page
        # dimensions/order only when the exact one-based page is unavailable.
        ordered = sorted(raw_pages)
        if page.page_index < len(ordered):
            mapping[page.page_index] = ordered[page.page_index]
    return mapping


def _raw_span_refs(raw_page: Mapping[str, Any]) -> list[SourceSpanRef]:
    blocks = list(raw_page.get("blocks", []) or [])
    refs: list[SourceSpanRef] = []
    for raw_span in raw_page.get("spans", []) or []:
        bbox = tuple(float(value) for value in raw_span.get("bbox", (0, 0, 0, 0)))
        block_index: int | None = None
        for block in blocks:
            block_bbox = tuple(float(value) for value in block.get("bbox", (0, 0, 0, 0)))
            if _contains(block_bbox, bbox):
                block_index = int(block.get("index"))
                break
        refs.append(SourceSpanRef(
            pdf_page_number=int(raw_page["pdf_page_number"]),
            span_index=int(raw_span.get("index", len(refs))),
            text=str(raw_span.get("text") or ""),
            bbox=bbox, block_index=block_index,
        ))
    return refs


def _raw_bbox(block: MarkerBlock, raw_page: Mapping[str, Any]) -> BBox:
    return scale_bbox(
        block.bbox,
        from_width=block.page_width,
        from_height=block.page_height,
        to_width=float(raw_page.get("width") or block.page_width),
        to_height=float(raw_page.get("height") or block.page_height),
    )


def align_marker_blocks(
    marker: MarkerDocument,
    raw_document: Mapping[str, Any],
    *,
    minimum_overlap: float = 0.08,
) -> AlignmentResult:
    """Align layout blocks to existing raw spans without fabricating spans."""
    raw_pages = {int(page.get("pdf_page_number")): page for page in raw_document.get("pages", [])}
    page_mapping = _page_index_map(marker, raw_document)
    aligned: list[AlignedBlock] = []
    for page in marker.pages:
        pdf_page = page_mapping.get(page.page_index)
        if pdf_page is None or pdf_page not in raw_pages:
            aligned.extend(AlignedBlock(block, status="unresolved") for block in page.blocks)
            continue
        raw_page = raw_pages[pdf_page]
        refs = _raw_span_refs(raw_page)
        for block in page.blocks:
            target = _raw_bbox(block, raw_page)
            candidates: list[tuple[float, float, SourceSpanRef]] = []
            for ref in refs:
                ratio = overlap_ratio(target, ref.bbox)
                center_hit = _contains(target, ref.bbox)
                similarity = _text_similarity(block.text, ref.text)
                if ratio >= minimum_overlap or center_hit or similarity >= 0.65:
                    candidates.append((ratio, similarity, ref))
            candidates.sort(key=lambda item: (item[2].bbox[1], item[2].bbox[0], item[2].span_index))
            selected = tuple(item[2] for item in candidates)
            max_overlap = max((item[0] for item in candidates), default=0.0)
            max_similarity = max((item[1] for item in candidates), default=0.0)
            if block.is_table or block.is_picture:
                status = "aligned" if selected else "unresolved"
            else:
                status = "aligned" if selected and (max_overlap >= 0.18 or max_similarity >= 0.65) else "unresolved"
            aligned.append(AlignedBlock(
                marker=block,
                source_spans=selected,
                status=status,
                overlap_ratio=max_overlap,
                text_similarity=max_similarity,
            ))
    return AlignmentResult(blocks=tuple(aligned), page_mapping=page_mapping)

