import re

from app.services.knowledge.layout import SourceBlock, SourceTable
from app.services.knowledge.types import SourceRef, VocabularyRecord
from app.services.normalization import normalize_korean_key

_KOREAN = re.compile(r"[\uac00-\ud7a3]")
_LATIN = re.compile(r"[A-Za-zÀ-ỹ]")
_BILINGUAL_CELL = re.compile(
    r"^\s*(?P<headword>.*[\uac00-\ud7a3])\s+(?P<meaning>[A-Za-zÀ-ỹ].+?)\s*$",
    re.S,
)


def normalize_headword(text: str) -> str:
    return normalize_korean_key(text)


def _append_record(
    records: list[VocabularyRecord],
    seen: set[tuple[str, str]],
    *,
    headword: str,
    meaning: str,
    source: SourceRef,
) -> None:
    headword = " ".join(headword.split())
    meaning = " ".join(meaning.split())
    key = (normalize_headword(headword), meaning.casefold())
    if not headword or not meaning or key in seen:
        return
    seen.add(key)
    records.append(VocabularyRecord(
        source=source,
        headword=headword,
        normalized_headword=normalize_headword(headword),
        meanings_vi=[meaning],
    ))


def extract_vocabulary(
    tables: list[SourceTable],
    blocks: list[SourceBlock] | None = None,
) -> list[VocabularyRecord]:
    records: list[VocabularyRecord] = []
    seen: set[tuple[str, str]] = set()
    for table in tables:
        for row_index, row in enumerate(table.rows):
            cells = [cell for cell in row if cell]
            for cell in cells:
                match = _BILINGUAL_CELL.match(cell)
                if match:
                    _append_record(
                        records, seen,
                        headword=match.group("headword"),
                        meaning=match.group("meaning"),
                        source=SourceRef(
                            pdf_page_number=table.page_number,
                            printed_page_number=table.printed_page_number,
                            table_index=table.table_index,
                            table_row_index=row_index,
                        ),
                    )
            if len(cells) < 2:
                continue
            # Accept explicit Korean/Vietnamese adjacent pairs only. Unknown
            # columns are left for review rather than guessed by position alone.
            for index, cell in enumerate(cells[:-1]):
                if not _KOREAN.search(cell) or _KOREAN.search(cells[index + 1]):
                    continue
                meaning = cells[index + 1]
                if not _LATIN.search(meaning):
                    continue
                _append_record(
                    records, seen, headword=cell, meaning=meaning,
                    source=SourceRef(
                        pdf_page_number=table.page_number,
                        printed_page_number=table.printed_page_number,
                        table_index=table.table_index,
                        table_row_index=row_index,
                    ),
                )

    if blocks:
        pages_with_glossary = {
            block.page_number for block in blocks
            if " ".join(block.text.split()) == "새 단어"
        }
        for page_number in pages_with_glossary:
            page_blocks = [
                block for block in blocks
                if block.page_number == page_number
                and not block.is_header_footer_candidate
                and block.text.strip() != "새 단어"
            ]
            if not page_blocks:
                continue
            width = page_blocks[0].page_width or 1
            for column in range(3):
                column_blocks = sorted(
                    (
                        block for block in page_blocks
                        if min(2, int((block.bbox[0] / width) * 3)) == column
                    ),
                    key=lambda block: (block.bbox[1], block.bbox[0]),
                )
                active: SourceBlock | None = None
                meanings: list[str] = []

                def flush() -> None:
                    nonlocal active, meanings
                    if active is not None and meanings:
                        _append_record(
                            records, seen,
                            headword=active.text,
                            meaning=" ".join(meanings),
                            source=SourceRef(
                                active.page_number, active.printed_page_number,
                                active.block_index,
                            ),
                        )
                    active, meanings = None, []

                for block in column_blocks:
                    text = " ".join(block.text.split())
                    if _KOREAN.search(text) and not _LATIN.search(text) and len(text) <= 40:
                        flush()
                        active = block
                    elif active is not None and _LATIN.search(text):
                        meanings.append(text)
                flush()
    return records
