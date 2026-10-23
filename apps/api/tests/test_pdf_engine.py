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


def test_pymupdf_extracts_page_blocks_and_korean_vietnamese(tmp_path: Path):
    fitz = pytest.importorskip("fitz")
    font_path = Path("C:/Windows/Fonts/malgun.ttf")
    if not font_path.exists():
        pytest.skip("A Korean-capable system font is unavailable for this integration fixture")
    path = tmp_path / "source.pdf"
    document = fitz.open()
    page = document.new_page()
    page.insert_font(fontname="Korean", fontfile=str(font_path))
    page.insert_text((72, 72), "제 1과 유행\n안녕하세요\nXin chào", fontname="Korean")
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
    page.insert_text((178, 170), "book", fontname="Korean")
    image = fitz.Pixmap(fitz.csRGB, fitz.IRect(0, 0, 2, 2), False)
    image.clear_with(0x336699)
    page.insert_image(fitz.Rect(300, 72, 340, 112), pixmap=image)
    document.save(path)
    document.close()

    assert inspect_pdf(path) == 1
    extracted = extract_pages(path)
    assert extracted[0].pdf_page_number == 1
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
