import re

from app.services.knowledge.layout import SourceTable
from app.services.knowledge.types import SourceRef, VocabularyRecord
from app.services.normalization import normalize_korean_key

_KOREAN = re.compile(r"[\uac00-\ud7a3]")
_LATIN = re.compile(r"[A-Za-zÀ-ỹ]")


def normalize_headword(text: str) -> str:
    return normalize_korean_key(text)


def extract_vocabulary(tables: list[SourceTable]) -> list[VocabularyRecord]:
    records: list[VocabularyRecord] = []
    seen: set[tuple[str, str]] = set()
    for table in tables:
        for row_index, row in enumerate(table.rows):
            cells = [cell for cell in row if cell]
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
                key = (normalize_headword(cell), meaning.casefold())
                if key in seen:
                    continue
                seen.add(key)
                records.append(VocabularyRecord(
                    source=SourceRef(
                        pdf_page_number=table.page_number,
                        printed_page_number=table.printed_page_number,
                        table_index=table.table_index,
                        table_row_index=row_index,
                    ),
                    headword=cell,
                    normalized_headword=normalize_headword(cell),
                    meanings_vi=[meaning],
                ))
    return records
