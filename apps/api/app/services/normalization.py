"""Conservative normalization for Korean-learning source data.

Display text uses NFC so compatibility characters are not silently rewritten.
Identifiers use NFKC because they are machine keys rather than source prose.
"""
from __future__ import annotations

import re
import unicodedata

_INLINE_SPACE = re.compile(r"[^\S\r\n]+")
_BLANK_LINES = re.compile(r"\n{3,}")
_IDENTIFIER_NOISE = re.compile(r"[^0-9A-Z가-힣._-]+")


def normalize_source_text(value: str) -> str:
    """Remove unsafe controls while preserving Korean/Vietnamese meaning and lines."""
    value = unicodedata.normalize("NFC", value.replace("\r\n", "\n").replace("\r", "\n"))
    value = "".join(
        character
        for character in value
        if character in "\n\t" or unicodedata.category(character) not in {"Cc", "Cs"}
    )
    lines = [_INLINE_SPACE.sub(" ", line).strip() for line in value.split("\n")]
    return _BLANK_LINES.sub("\n\n", "\n".join(lines)).strip()


def normalize_korean_key(value: str) -> str:
    """Build a stable comparison key without changing the stored source string."""
    return " ".join(normalize_source_text(value).split()).casefold()


def normalize_identifier(value: str, *, prefix: str | None = None) -> str:
    normalized = unicodedata.normalize("NFKC", value).upper().strip()
    normalized = _IDENTIFIER_NOISE.sub("", normalized)
    if prefix and normalized and not normalized.startswith(prefix.upper()):
        normalized = f"{prefix.upper()}{normalized}"
    return normalized or "UNKNOWN"


def normalize_track_id(value: str) -> str:
    compact = normalize_identifier(value).replace(".", "").replace("_", "").replace("-", "")
    match = re.fullmatch(r"(?:CD)?(\d+)(?:TRACK|TR|T)(\d+)", compact)
    if match:
        return f"CD{int(match.group(1))}TRACK{int(match.group(2)):02d}"
    return compact


def normalize_source_reference(
    document_sha256: str,
    pdf_page_number: int,
    block_index: int | None = None,
    table_index: int | None = None,
    table_row_index: int | None = None,
) -> str:
    parts = [document_sha256.lower(), f"p{pdf_page_number}"]
    if block_index is not None:
        parts.append(f"b{block_index}")
    if table_index is not None:
        parts.append(f"t{table_index}")
    if table_row_index is not None:
        parts.append(f"r{table_row_index}")
    return ":".join(parts)
