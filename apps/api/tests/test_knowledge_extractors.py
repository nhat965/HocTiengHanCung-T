import json
from hashlib import sha256
from pathlib import Path

import pytest
from sqlalchemy import func, select

from app import database
from app.models import Lesson, SourceBlock, SourceDocument, SourcePage, SourceSpan, Textbook, Vocabulary
from app.services.knowledge.layout import SourceTable, ordered_blocks
from app.services.knowledge.pipeline import extract_knowledge, write_knowledge_json
from app.services.knowledge.persistence import persist_bundle
from app.services.knowledge.vocabulary import extract_vocabulary


def test_layout_orders_columns_and_preserves_full_width_anchors():
    page = {
        "pdf_page_number": 1,
        "width": 600,
        "height": 800,
        "blocks": [
            {"index": 0, "text": "Heading", "bbox": [20, 20, 580, 40]},
            {"index": 1, "text": "left 1", "bbox": [30, 80, 260, 100]},
            {"index": 2, "text": "right 1", "bbox": [330, 82, 560, 102]},
            {"index": 3, "text": "left 2", "bbox": [30, 120, 260, 140]},
            {"index": 4, "text": "right 2", "bbox": [330, 122, 560, 142]},
            {"index": 5, "text": "Subheading", "bbox": [20, 180, 580, 200]},
            {"index": 6, "text": "left 3", "bbox": [30, 220, 260, 240]},
            {"index": 7, "text": "right 3", "bbox": [330, 222, 560, 242]},
        ],
    }

    assert [block.text for block in ordered_blocks(page)] == [
        "Heading", "left 1", "left 2", "right 1", "right 2",
        "Subheading", "left 3", "right 3",
    ]


def test_vocabulary_pairs_repeated_korean_vietnamese_columns():
    table = SourceTable(
        page_number=12,
        printed_page_number="11",
        table_index=2,
        bbox=(0, 0, 600, 400),
        rows=[["사과", "quả táo", "가다", "đi"]],
    )

    records = extract_vocabulary([table])

    assert [(item.headword, item.meanings_vi) for item in records] == [
        ("사과", ["quả táo"]),
        ("가다", ["đi"]),
    ]
    assert all(item.source.table_row_index == 0 for item in records)


def test_lesson_detection_skips_toc_pages_and_running_headers():
    raw = {
        "source": {"page_count": 3},
        "pages": [
            {
                "pdf_page_number": 1,
                "width": 600,
                "height": 800,
                "blocks": [
                    {"index": 0, "text": "목차", "bbox": [50, 30, 100, 50]},
                    {"index": 1, "text": "01 유행", "bbox": [50, 100, 200, 120]},
                ],
                "tables": [],
            },
            {
                "pdf_page_number": 2,
                "width": 600,
                "height": 800,
                "blocks": [
                    {
                        "index": 0,
                        "text": "01 유행",
                        "bbox": [50, 30, 200, 50],
                        "is_header_footer_candidate": True,
                    },
                ],
                "tables": [],
            },
            {
                "pdf_page_number": 3,
                "width": 600,
                "height": 800,
                "blocks": [
                    {"index": 0, "text": "01 유행", "bbox": [50, 100, 200, 120]},
                ],
                "tables": [],
            },
        ],
    }

    bundle = extract_knowledge(raw)

    assert [(item.start_pdf_page, item.end_pdf_page) for item in bundle.lessons] == [(3, 3)]


def test_pipeline_excludes_contents_pages_and_repeated_running_headers():
    raw = {
        "source": {"page_count": 3},
        "pages": [
            {
                "pdf_page_number": 1,
                "width": 600,
                "height": 800,
                "blocks": [
                    {"index": 0, "text": "목차", "bbox": [50, 20, 100, 40]},
                    {"index": 1, "text": "GRAMMAR: fake || fake", "bbox": [50, 60, 300, 80]},
                    {"index": 2, "text": "READING[fake]: fake", "bbox": [50, 90, 300, 110]},
                ],
                "tables": [],
            },
            {
                "pdf_page_number": 2,
                "width": 600,
                "height": 800,
                "blocks": [
                    {"index": 0, "text": "01 유행", "bbox": [50, 120, 200, 140]},
                    {
                        "index": 1,
                        "text": "GRAMMAR: running header || not content",
                        "bbox": [50, 20, 300, 40],
                        "is_header_footer_candidate": True,
                    },
                    {"index": 2, "text": "문법", "bbox": [50, 180, 120, 200]},
                ],
                "tables": [],
            },
            {
                "pdf_page_number": 3,
                "width": 600,
                "height": 800,
                "blocks": [
                    {"index": 0, "text": "GRAMMAR: running header || not content", "bbox": [50, 20, 300, 40],
                     "is_header_footer_candidate": True},
                    {"index": 1, "text": "EXAMPLE: 문장을 씁니다. || Viết câu.", "bbox": [50, 180, 300, 200]},
                ],
                "tables": [],
            },
        ],
    }

    bundle = extract_knowledge(raw)

    assert [item.ordinal for item in bundle.lessons] == [1]
    assert not bundle.passages
    assert not bundle.grammar
    assert any("Skipped likely table-of-contents pages: 1" in warning for warning in bundle.warnings)
    assert any("Filtered 1 repeated header/footer" in warning for warning in bundle.warnings)


def test_extractors_create_source_linked_fixture_records(tmp_path: Path, client):
    raw = {
        "schema_version": 1,
        "source": {"filename": "synthetic.pdf", "sha256": "abc123", "page_count": 2},
        "pages": [
            {
                "pdf_page_number": 1,
                "printed_page_number": "1",
                "width": 600,
                "height": 800,
                "blocks": [
                    {"index": 3, "text": "01 유행", "bbox": [50, 40, 300, 65]},
                    {"index": 2, "text": "문법", "bbox": [50, 100, 120, 120]},
                    {"index": 4, "text": "GRAMMAR: -아/어 보다 || thử làm", "bbox": [50, 140, 400, 160]},
                    {"index": 5, "text": "EXAMPLE: 책을 읽어 봐요. || Tôi thử đọc sách.", "bbox": [50, 170, 400, 190]},
                    {"index": 6, "text": "DIALOGUE[dlg1]: At a cafe", "bbox": [50, 220, 400, 240]},
                    {"index": 7, "text": "민수: 커피 주세요. || Cho tôi cà phê.", "bbox": [50, 250, 400, 270]},
                    {"index": 8, "text": "영희: 여기 있습니다. || Đây ạ.", "bbox": [50, 280, 400, 300]},
                    {"index": 9, "text": "READING[read1]: A short story", "bbox": [50, 330, 400, 350]},
                    {"index": 10, "text": "PARAGRAPH: 첫 번째 문단입니다.", "bbox": [50, 360, 400, 380]},
                    {"index": 11, "text": "PARAGRAPH: 두 번째 문단입니다.", "bbox": [50, 390, 400, 410]},
                    {"index": 12, "text": "EXERCISE[grp1]: multiple_choice || 알맞은 답을 고르세요", "bbox": [50, 440, 500, 460]},
                    {"index": 13, "text": "Q1: 빈칸에 알맞은 것을 고르세요.", "bbox": [50, 470, 500, 490]},
                    {"index": 14, "text": "OPTION: 보기 하나", "bbox": [60, 500, 300, 520]},
                    {"index": 15, "text": "OPTION: 보기 둘", "bbox": [60, 530, 300, 550]},
                    {"index": 16, "text": "CD1 TRACK 01", "bbox": [50, 580, 200, 600]},
                    {"index": 17, "text": "TRANSCRIPT[CD1TRACK01]: 안녕하세요.", "bbox": [50, 610, 450, 630]},
                ],
                "tables": [
                    {
                        "index": 0,
                        "bbox": [50, 50, 550, 120],
                        "rows": [
                            ["사과", "quả táo", "가다", "đi"],
                        ],
                    }
                ],
            },
            {
                "pdf_page_number": 2,
                "printed_page_number": "2",
                "width": 600,
                "height": 800,
                "blocks": [
                    {"index": 0, "text": "ANSWER[q1]: A", "bbox": [50, 120, 300, 140]},
                ],
                "tables": [],
            },
        ],
    }

    bundle = extract_knowledge(raw)

    assert [(item.ordinal, item.title_ko, item.start_pdf_page, item.end_pdf_page) for item in bundle.lessons] == [
        (1, "유행", 1, 2)
    ]
    assert len(bundle.vocabulary) == 2
    assert bundle.vocabulary[0].headword == "사과"
    assert bundle.vocabulary[0].meanings_vi == ["quả táo"]
    assert bundle.vocabulary[0].source.table_index == 0
    assert bundle.grammar[0].pattern == "-아/어 보다"
    assert bundle.grammar[0].example_ids == ["sentence-1"]
    assert bundle.sentences[0].grammar_patterns == ["-아/어 보다"]
    assert [turn.turn_index for turn in bundle.dialogue_turns] == [0, 1]
    assert len(bundle.passages[0].paragraphs) == 2
    question = next(item for item in bundle.exercises if item.local_id == "grp1.q1")
    assert question.exercise_type == "multiple_choice"
    assert len(question.options) == 2
    assert question.answer == "A"
    assert question.answer_source.pdf_page_number == 2
    assert bundle.listening_tracks[0].track_identifier == "CD1TRACK01"
    assert bundle.transcripts[0].track_identifier == "CD1TRACK01"
    assert not [warning for warning in bundle.warnings if "Transcript not found" in warning]

    output = tmp_path / "knowledge.json"
    write_knowledge_json(bundle, output, raw["source"])
    encoded = json.loads(output.read_text(encoding="utf-8"))
    assert encoded["schema_version"] == 1
    assert encoded["source"]["filename"] == "synthetic.pdf"
    assert encoded["data"]["vocabulary"][0]["source"]["pdf_page_number"] == 1

    with database.SessionLocal() as session:
        textbook = Textbook(owner_id="test-owner", title="Synthetic", level="intermediate", volume_number=4)
        session.add(textbook)
        session.flush()
        source_document = SourceDocument(
            owner_id="test-owner",
            textbook_id=textbook.id,
            filename="synthetic.pdf",
            sha256=sha256(b"synthetic").hexdigest(),
            page_count=2,
            source_path=str(tmp_path / "synthetic.pdf"),
        )
        session.add(source_document)
        session.flush()
        for raw_page in raw["pages"]:
            page = SourcePage(
                source_document_id=source_document.id,
                pdf_page_number=raw_page["pdf_page_number"],
                printed_page_number=raw_page["printed_page_number"],
                raw_text="synthetic fixture",
            )
            session.add(page)
            session.flush()
            for block in raw_page["blocks"]:
                source_block = SourceBlock(
                    source_page_id=page.id,
                    block_index=block["index"],
                    text=block["text"],
                    x0=block["bbox"][0],
                    y0=block["bbox"][1],
                    x1=block["bbox"][2],
                    y1=block["bbox"][3],
                )
                session.add(source_block)
                session.flush()
                session.add(SourceSpan(
                    source_page_id=page.id,
                    source_block_id=source_block.id,
                    label="raw_block",
                    raw_text=block["text"],
                    normalized_text=block["text"],
                    confidence=0,
                    review_status="pending",
                ))
            for table in raw_page["tables"]:
                for row_index, row in enumerate(table["rows"]):
                    raw_row = " | ".join(cell or "" for cell in row)
                    session.add(SourceSpan(
                        source_page_id=page.id,
                        label=f"raw_table:{table['index']}:{row_index}",
                        raw_text=raw_row,
                        normalized_text=raw_row,
                        confidence=0,
                        review_status="pending",
                    ))
        duplicate_source = SourceDocument(
            owner_id="test-owner",
            textbook_id=textbook.id,
            filename="duplicate.pdf",
            sha256=sha256(b"another source").hexdigest(),
            page_count=1,
            source_path=str(tmp_path / "duplicate.pdf"),
        )
        session.add(duplicate_source)
        session.flush()
        session.add(SourcePage(
            source_document_id=duplicate_source.id,
            pdf_page_number=1,
            raw_text="separate source",
        ))
        session.commit()

        with pytest.raises(ValueError, match="source_document_id is required"):
            persist_bundle(session, textbook.id, bundle)
        first_counts = persist_bundle(session, textbook.id, bundle, source_document.id)
        session.commit()
        vocabulary = session.scalar(select(Vocabulary).where(Vocabulary.headword == "사과"))
        assert vocabulary is not None
        vocabulary.headword = "Reviewed headword"
        vocabulary.review_status = "approved"
        session.commit()

        second_counts = persist_bundle(session, textbook.id, bundle, source_document.id)
        session.commit()
        assert second_counts["lessons"] == 0
        assert second_counts["vocabulary"] == 0
        assert second_counts["grammar"] == 0
        assert second_counts["sentences"] == 0
        assert session.scalar(select(func.count(Lesson.id))) == 1
        assert session.scalar(select(func.count(Vocabulary.id))) == 2
        assert session.scalar(select(Vocabulary).where(Vocabulary.id == vocabulary.id)).headword == "Reviewed headword"
        assert first_counts["lessons"] == 1
        assert first_counts["vocabulary"] == 2
        lesson_id = session.scalar(select(Lesson.id))
        client_session_book_id = textbook.id

    assert client.get(f"/api/v1/textbooks/{client_session_book_id}/lessons").status_code == 200
    assert client.get(f"/api/v1/lessons/{lesson_id}/vocabulary").json()[0]["meanings_vi"]
    assert client.get(f"/api/v1/lessons/{lesson_id}/grammar").json()[0]["source_page_number"] == 1
    assert client.get(f"/api/v1/lessons/{lesson_id}/sentences").status_code == 200
    assert client.get(f"/api/v1/lessons/{lesson_id}/reading").status_code == 200
    assert client.get(f"/api/v1/lessons/{lesson_id}/listening").json()[0]["audio_status"] == "missing"
    assert client.get(f"/api/v1/lessons/{lesson_id}/exercises").status_code == 200
