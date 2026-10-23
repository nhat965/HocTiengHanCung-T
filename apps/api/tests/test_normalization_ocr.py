from app.services.normalization import (
    normalize_korean_key,
    normalize_source_reference,
    normalize_source_text,
    normalize_track_id,
)
from app.services.ocr import DisabledOcrAdapter, should_request_ocr


def test_unicode_normalization_preserves_korean_and_vietnamese_semantics():
    decomposed = "ha\u0300n\x00  quốc\n\n\n한국\t 사람"
    normalized = normalize_source_text(decomposed)
    assert normalized == "hàn quốc\n\n한국 사람"
    assert normalize_korean_key("한국   사람") == "한국 사람"


def test_identifiers_and_source_references_are_stable():
    assert normalize_track_id("cd １ - track 2") == "CD1TRACK02"
    assert normalize_source_reference("ABCDEF", 7, block_index=2, table_index=1, table_row_index=3) == "abcdef:p7:b2:t1:r3"


def test_ocr_adapter_marks_unreadable_content_without_guessing():
    assert should_request_ocr(extracted_text="", image_count=1)
    assert not should_request_ocr(extracted_text="한국어 텍스트가 충분히 있습니다 123", image_count=1)
    result = DisabledOcrAdapter().recognize_page(b"image", page_number=1)
    assert result.status == "unresolved"
    assert result.regions == []
    assert result.unreadable_regions == 1
