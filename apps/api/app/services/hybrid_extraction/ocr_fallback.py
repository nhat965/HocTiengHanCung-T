from __future__ import annotations

from typing import Any, Iterable, Mapping

from app.services.hybrid_extraction.types import (
    BBox,
    MarkerDocument,
    OcrRegionOutcome,
    OcrRegionRequest,
)
from app.services.ocr import DisabledOcrAdapter, OcrAdapter, OcrResult


def plan_ocr_regions(
    raw_document: Mapping[str, Any],
    marker: MarkerDocument,
) -> tuple[OcrRegionRequest, ...]:
    """Plan only image regions that lack useful text-layer evidence."""
    raw_pages = {int(page.get("pdf_page_number")): page for page in raw_document.get("pages", [])}
    requests: list[OcrRegionRequest] = []
    for page in marker.pages:
        raw_page = raw_pages.get(page.pdf_page_number)
        if raw_page is None:
            continue
        page_needs_ocr = bool(raw_page.get("needs_ocr"))
        for image in raw_page.get("images", []) or []:
            bbox = tuple(float(value) for value in image.get("bbox", (0, 0, 0, 0)))
            nearby_text = any(
                _overlap(bbox, tuple(float(value) for value in span.get("bbox", (0, 0, 0, 0)))) > 0.05
                for span in raw_page.get("spans", []) or []
            )
            picture_blocks = [
                block for block in page.blocks
                if block.is_picture and _overlap(block.bbox, bbox) > 0.05
            ]
            if page_needs_ocr or (picture_blocks and not nearby_text):
                requests.append(OcrRegionRequest(
                    pdf_page_number=page.pdf_page_number,
                    bbox=bbox,
                    reason="text-layer-missing-or-image-only",
                    source_image_index=int(image.get("index", 0)),
                ))
    return tuple(requests)


def _overlap(left: BBox, right: BBox) -> float:
    width = max(0.0, min(left[2], right[2]) - max(left[0], right[0]))
    height = max(0.0, min(left[3], right[3]) - max(left[1], right[1]))
    area = max(0.0, left[2] - left[0]) * max(0.0, left[3] - left[1])
    return width * height / area if area else 0.0


def _outcome(request: OcrRegionRequest, result: OcrResult) -> OcrRegionOutcome:
    text = " ".join(region.text.strip() for region in result.regions if region.text.strip()).strip() or None
    status = result.status if result.status in {"resolved", "unresolved", "needs_review"} else "needs_review"
    return OcrRegionOutcome(request=request, status=status, text=text, message=result.message)


def run_ocr_regions(
    requests: Iterable[OcrRegionRequest],
    *,
    adapter: OcrAdapter | None = None,
    images: Mapping[tuple[int, int], bytes] | None = None,
) -> tuple[OcrRegionOutcome, ...]:
    """Run a configured adapter, preserving unresolved regions by default.

    ``OcrAdapter`` currently accepts a page/image payload, so a region request
    passes its source image and keeps the region bbox as provenance.  OCR text
    is never inserted into the knowledge bundle automatically.
    """
    selected = adapter or DisabledOcrAdapter()
    payloads = images or {}
    outcomes: list[OcrRegionOutcome] = []
    for request in requests:
        payload = payloads.get((request.pdf_page_number, request.source_image_index or 0), b"")
        try:
            result = selected.recognize_page(payload, page_number=request.pdf_page_number)
        except Exception as error:  # OCR is an optional review signal, never a job failure.
            outcomes.append(OcrRegionOutcome(
                request=request,
                status="unresolved",
                message=f"OCR adapter failed: {error.__class__.__name__}",
            ))
            continue
        outcomes.append(_outcome(request, result))
    return tuple(outcomes)

