from __future__ import annotations

from app.services.hybrid_extraction.layout_alignment import align_marker_blocks
from app.services.hybrid_extraction.marker_adapter import parse_marker_document
from app.services.hybrid_extraction.pipeline import extract_hybrid
from app.services.hybrid_extraction.table_recovery import (
    apply_table_recovery,
    recover_marker_tables,
)


def _page(children, *, page_index: int = 17):
    return {
        "block_type": "Page",
        "id": f"/page/{page_index}/Page/1",
        "bbox": [0, 0, 400, 400],
        "polygon": [[0, 0], [400, 0], [400, 400], [0, 400]],
        "children": children,
    }


def _raw_page(*, spans, tables=None, images=None, needs_ocr=False, page_number=18):
    return {
        "pdf_page_number": page_number,
        "printed_page_number": str(page_number),
        "width": 400,
        "height": 400,
        "blocks": [],
        "spans": spans,
        "tables": tables or [],
        "images": images or [],
        "needs_ocr": needs_ocr,
    }


def test_marker_page_index_maps_to_one_based_pdf_page():
    marker = parse_marker_document({"children": [_page([])]})

    assert marker.pages[0].page_index == 17
    assert marker.pages[0].pdf_page_number == 18


def test_marker_block_can_align_to_multiple_raw_spans():
    marker = parse_marker_document({"children": [_page([{
        "block_type": "Text",
        "id": "/page/17/Text/1",
        "bbox": [20, 20, 180, 45],
        "polygon": [[20, 20], [180, 20], [180, 45], [20, 45]],
        "html": "<p>한국어 문장</p>",
    }])]})
    raw = {"pages": [_raw_page(spans=[
        {"index": 3, "text": "한국어", "bbox": [20, 20, 90, 45]},
        {"index": 4, "text": "문장", "bbox": [95, 20, 180, 45]},
    ])]}

    result = align_marker_blocks(marker, raw)

    assert result.page_mapping == {17: 18}
    assert len(result.aligned_blocks) == 1
    assert [item.span_index for item in result.aligned_blocks[0].source_spans] == [3, 4]


def test_table_recovery_fills_missing_vietnamese_from_raw_spans_without_guessing():
    marker = parse_marker_document({"children": [_page([{
        "block_type": "Table",
        "id": "/page/17/Table/1",
        "bbox": [0, 0, 400, 160],
        "polygon": [[0, 0], [400, 0], [400, 160], [0, 160]],
        "html": "<table><tr><td>사과</td><td></td></tr><tr><td>가다</td><td></td></tr></table>",
    }])]})
    raw = {"pages": [_raw_page(
        spans=[
            {"index": 0, "text": "사과", "bbox": [20, 20, 70, 30]},
            {"index": 1, "text": "quả táo", "bbox": [220, 20, 290, 30]},
            {"index": 2, "text": "가다", "bbox": [20, 80, 60, 90]},
            {"index": 3, "text": "đi", "bbox": [220, 80, 240, 90]},
        ],
        tables=[{"index": 0, "bbox": [0, 0, 400, 160], "rows": [[None, None], [None, None]]}],
    )]}

    recovery = recover_marker_tables(marker, raw)
    merged = apply_table_recovery(raw, recovery)

    assert merged["pages"][0]["tables"][0]["rows"] == [
        ["사과", "quả táo"],
        ["가다", "đi"],
    ]
    recovered = [cell for cell in recovery.cells if cell.status == "recovered"]
    assert {cell.text for cell in recovered} >= {"quả táo", "đi"}
    assert all(cell.source_spans for cell in recovered)


def test_table_recovery_keeps_close_rows_separate():
    marker = parse_marker_document({"children": [_page([{
        "block_type": "Table",
        "id": "/page/17/Table/1",
        "bbox": [0, 0, 400, 100],
        "polygon": [[0, 0], [400, 0], [400, 100], [0, 100]],
        "html": "<table><tr><td>한국어 A</td><td></td></tr><tr><td>한국어 B</td><td></td></tr></table>",
    }])]})
    raw = {"pages": [_raw_page(
        spans=[
            {"index": 0, "text": "한국어 A", "bbox": [20, 20, 90, 28]},
            {"index": 1, "text": "meaning A", "bbox": [220, 20, 290, 28]},
            {"index": 2, "text": "한국어 B", "bbox": [20, 42, 90, 50]},
            {"index": 3, "text": "meaning B", "bbox": [220, 42, 290, 50]},
        ],
        tables=[{"index": 0, "bbox": [0, 0, 400, 100], "rows": [[None, None], [None, None]]}],
    )]}

    recovery = recover_marker_tables(marker, raw)

    assert recovery.tables[0].rows[0][1] == "meaning A"
    assert recovery.tables[0].rows[1][1] == "meaning B"


def test_ocr_unavailable_is_review_only_and_does_not_create_text():
    marker = {"children": [_page([{
        "block_type": "Picture",
        "id": "/page/17/Picture/1",
        "bbox": [10, 10, 200, 200],
        "polygon": [[10, 10], [200, 10], [200, 200], [10, 200]],
        "html": "",
    }])]}
    raw = {"pages": [_raw_page(
        spans=[],
        images=[{"index": 0, "bbox": [10, 10, 200, 200]}],
        needs_ocr=True,
    )]}

    result = extract_hybrid(raw, marker, run_ocr=True)

    assert len(result.ocr_outcomes) == 1
    assert result.ocr_outcomes[0].status == "unresolved"
    assert result.ocr_outcomes[0].text is None
    assert result.quality.ocr_regions_unresolved == 1


def test_hybrid_bridge_reuses_existing_parser_and_does_not_invent_answer():
    raw = {"source": {"page_count": 1}, "pages": [{
        **_raw_page(spans=[], page_number=1),
        "blocks": [{
            "index": 0,
            "text": "EXERCISE[lesson1]: multiple_choice || 알맞은 답을 고르세요",
            "bbox": [20, 20, 300, 40],
        }, {
            "index": 1,
            "text": "Q1: 빈칸에 알맞은 것을 고르세요.",
            "bbox": [20, 50, 300, 70],
        }, {
            "index": 2,
            "text": "OPTION: 하나",
            "bbox": [20, 80, 200, 100],
        }, {
            "index": 3,
            "text": "OPTION: 둘",
            "bbox": [20, 110, 200, 130],
        }],
        "tables": [],
    }]}

    result = extract_hybrid(raw)

    assert result.bundle.exercises
    question = next(item for item in result.bundle.exercises if item.local_id == "lesson1.q1")
    assert [option.text for option in question.options] == ["하나", "둘"]
    assert question.answer is None
    assert question.answer_source is None

