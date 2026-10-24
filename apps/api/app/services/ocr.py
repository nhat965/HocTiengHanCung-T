"""Pluggable, region-preserving OCR contract.

The default adapter deliberately does not invent text. Deployments can supply an
adapter backed by Tesseract or a managed service without changing PDF extraction.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Protocol


@dataclass(frozen=True)
class OcrRegion:
    text: str
    bbox: tuple[float, float, float, float]
    confidence: float | None = None


@dataclass(frozen=True)
class OcrResult:
    status: str
    regions: list[OcrRegion] = field(default_factory=list)
    unreadable_regions: int = 0
    message: str | None = None


class OcrAdapter(Protocol):
    name: str

    def recognize_page(self, image: bytes, *, page_number: int) -> OcrResult: ...


class DisabledOcrAdapter:
    """Safe default: records unresolved OCR demand and returns no guessed text."""

    name = "disabled"

    def recognize_page(self, image: bytes, *, page_number: int) -> OcrResult:
        del image, page_number
        return OcrResult(
            status="unresolved",
            unreadable_regions=1,
            message="OCR adapter is not configured; source region requires review.",
        )


def should_request_ocr(*, extracted_text: str, image_count: int, unreadable_ratio: float = 0.0) -> bool:
    """Request OCR only for missing/clearly damaged text, never as blanket replacement."""
    useful_characters = sum(character.isalnum() for character in extracted_text)
    return image_count > 0 and (useful_characters < 12 or unreadable_ratio >= 0.35)
