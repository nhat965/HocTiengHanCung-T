import re

from app.services.knowledge.layout import SourceBlock
from app.services.knowledge.types import LessonRecord, SectionRecord, SourceRef

_LESSON_TITLE = re.compile(
    r"^\s*(?P<number>\d{1,2})\s+(?P<title>[\uac00-\ud7a3][\uac00-\ud7a3\s·-]{0,40})\s*$"
)
_TOC = re.compile(r"(?:목차|차례|mục\s*lục|contents)", re.I)
_SECTION_NAMES = {
    "vocabulary": ("어휘", "새 단어", "từ vựng", "từ mới"),
    "grammar": ("문법", "ngữ pháp"),
    "speaking": ("말하기", "nói"),
    "listening": ("듣기", "nghe"),
    "reading": ("읽기", "đọc"),
    "writing": ("쓰기", "viết"),
    "culture": ("문화", "văn hóa", "văn hoá"),
}


def detect_lessons(blocks: list[SourceBlock]) -> list[LessonRecord]:
    lessons: list[LessonRecord] = []
    toc_pages = {
        block.page_number for block in blocks
        if _TOC.search(block.text)
    }
    for block in blocks:
        if (
            block.page_number in toc_pages
            or block.is_header_footer_candidate
            or (block.page_height and block.bbox[1] > block.page_height * 0.4)
        ):
            continue
        if _TOC.search(block.text):
            continue
        match = _LESSON_TITLE.fullmatch(block.text)
        if not match:
            continue
        lessons.append(LessonRecord(
            source=SourceRef(block.page_number, block.printed_page_number, block.block_index),
            ordinal=int(match.group("number")),
            title_ko=" ".join(match.group("title").split()),
            start_pdf_page=block.page_number,
        ))
    unique: dict[tuple[int, str], LessonRecord] = {}
    for lesson in lessons:
        unique.setdefault((lesson.ordinal, lesson.title_ko), lesson)
    return list(unique.values())


def add_lesson_end_pages(lessons: list[LessonRecord], document_page_count: int) -> list[LessonRecord]:
    ordered = sorted(lessons, key=lambda item: item.start_pdf_page)
    result: list[LessonRecord] = []
    for index, lesson in enumerate(ordered):
        end = ordered[index + 1].start_pdf_page - 1 if index + 1 < len(ordered) else document_page_count
        result.append(LessonRecord(**{**lesson.__dict__, "end_pdf_page": end}))
    return result


def detect_sections(blocks: list[SourceBlock]) -> list[SectionRecord]:
    sections: list[SectionRecord] = []
    for block in blocks:
        normalized = " ".join(block.text.split()).strip(" :：-")
        folded = normalized.casefold()
        for section_type, labels in _SECTION_NAMES.items():
            if any(folded == label.casefold() or folded.startswith(label.casefold() + " ") for label in labels):
                sections.append(SectionRecord(
                    source=SourceRef(block.page_number, block.printed_page_number, block.block_index),
                    section_type=section_type,
                    title=normalized,
                ))
                break
    return sections
