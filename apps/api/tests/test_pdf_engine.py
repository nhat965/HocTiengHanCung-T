from pathlib import Path
import json

import pytest

from app.services.pdf_engine import (
    PdfValidationError,
    extract_document,
    extract_pages,
    inspect_pdf,
    write_extraction_json,
)
from app.text_sanitizer import sanitize_json, sanitize_text


def test_text_and_json_sanitizers_preserve_unicode_while_replacing_nul():
    assert sanitize_text("한국어 tiếng Việt\x00 text") == "한국어 tiếng Việt\uFFFD text"
    assert sanitize_json({"한글": ["tiếng Việt\x00", {"text": "한국어"}]}) == {
        "한글": ["tiếng Việt\uFFFD", {"text": "한국어"}],
    }


def test_pdf_text_replaces_postgresql_unsupported_nul_bytes():
    assert sanitize_text("before\x00after") == "before\uFFFDafter"


def test_pymupdf_extracts_page_blocks_and_korean_vietnamese(tmp_path: Path):
    fitz = pytest.importorskip("fitz")
    font_path = Path("C:/Windows/Fonts/malgun.ttf")
    if not font_path.exists():
        pytest.skip("A Korean-capable system font is unavailable for this integration fixture")
    path = tmp_path / "source.pdf"
    document = fitz.open()
    page = document.new_page()
    page.insert_font(fontname="Korean", fontfile=str(font_path))
    page.insert_text(
        (72, 72),
        "제 1과 유행\n안녕하세요\nXin chào",
        fontname="Korean",
    )
    page.insert_text((72, 105), "NUL before\x00after")
    for rect in (
        fitz.Rect(72, 120, 172, 150),
        fitz.Rect(172, 120, 272, 150),
        fitz.Rect(72, 150, 172, 180),
        fitz.Rect(172, 150, 272, 180),
    ):
        page.draw_rect(rect)
    page.insert_text((78, 140), "단어", fontname="Korean")
    page.insert_text((178, 140), "Meaning", fontname="Korean")
    page.insert_text((78, 170), "책", fontname="Korean")
    page.insert_text((178, 170), "book\x00NUL")
    image = fitz.Pixmap(fitz.csRGB, fitz.IRect(0, 0, 2, 2), False)
    image.clear_with(0x336699)
    page.insert_image(fitz.Rect(300, 72, 340, 112), pixmap=image)
    document.save(path)
    document.close()

    assert inspect_pdf(path) == 1
    extracted = extract_pages(path)
    assert extracted[0].pdf_page_number == 1
    assert extracted[0].sanitized_nul_count > 0
    assert "\uFFFD" in extracted[0].text
    assert "\x00" not in extracted[0].text
    assert all("\x00" not in block.text for block in extracted[0].blocks)
    assert all("\x00" not in span.text for span in extracted[0].spans)
    assert all(
        "\x00" not in cell
        for table in extracted[0].tables
        for row in table.rows
        for cell in row
        if cell is not None
    )
    assert extracted[0].blocks
    assert extracted[0].spans
    assert extracted[0].tables
    assert extracted[0].tables[0].rows
    assert extracted[0].images
    assert extracted[0].korean_character_count > 0
    assert extracted[0].vietnamese_character_count > 0

    json_path = write_extraction_json(extract_document(path), tmp_path / "extraction.json")
    payload = json.loads(json_path.read_text(encoding="utf-8"))
    page_payload = payload["pages"][0]
    assert payload["source"]["metadata"]
    assert page_payload["spans"][0]["bbox"]
    assert page_payload["tables"][0]["rows"]
    assert page_payload["images"][0]["asset_path"]
    assert (tmp_path / page_payload["images"][0]["asset_path"]).exists()


def test_corrupt_pdf_is_rejected(tmp_path: Path):
    source = tmp_path / "broken.pdf"
    source.write_bytes(b"not a PDF")
    with pytest.raises(PdfValidationError):
        inspect_pdf(source)
