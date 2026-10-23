"""Configurable lesson segmentation based on extracted source spans."""
from __future__ import annotations

from dataclasses import dataclass
import re


@dataclass(frozen=True)
class ExtractionProfile:
    name: str
    lesson_patterns: tuple[str, ...]
    section_patterns: dict[str, tuple[str, ...]]


DEFAULT_PROFILE = ExtractionProfile(
    name="generic-korean-textbook-v1",
    lesson_patterns=(r"(?:제\s*)?(\d{1,2})\s*과\s*[:：-]?\s*(.+)", r"Bài\s*(\d{1,2})\s*[:：-]?\s*(.+)"),
    section_patterns={
        "vocabulary": (r"어휘", r"새\s*단어", r"Từ\s*vựng"),
        "grammar": (r"문법", r"Ngữ\s*pháp"),
        "speaking": (r"말하기", r"Nói"),
        "listening": (r"듣기", r"Nghe"),
        "reading": (r"읽기", r"Đọc"),
        "writing": (r"쓰기", r"Viết"),
        "culture": (r"문화", r"Văn hóa"),
        "transcript": (r"대본", r"Transcript"),
        "answer_key": (r"정답", r"Đáp án"),
    },
)


@dataclass(frozen=True)
class LessonBoundary:
    ordinal: int
    title: str
    pdf_page_number: int
    confidence: float


def normalize_text(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


def detect_lesson_boundaries(page_text: dict[int, str], profile: ExtractionProfile = DEFAULT_PROFILE) -> list[LessonBoundary]:
    results: list[LessonBoundary] = []
    compiled = [re.compile(pattern, re.IGNORECASE | re.MULTILINE) for pattern in profile.lesson_patterns]
    for page_number, text in page_text.items():
        for pattern in compiled:
            match = pattern.search(text)
            if not match:
                continue
            ordinal = int(match.group(1))
            title = normalize_text(match.group(2))[:255]
            if title:
                results.append(LessonBoundary(ordinal=ordinal, title=title, pdf_page_number=page_number, confidence=0.72))
            break
    return results
