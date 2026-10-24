import json
from hashlib import sha256
from pathlib import Path

import pytest
from sqlalchemy import func, select

from app import database
from app.models import (
    AnswerKey,
    Exercise,
    ExerciseOption,
    Lesson,
    SourceBlock,
    SourceDocument,
    SourcePage,
    SourceSpan,
    Textbook,
    Vocabulary,
)
from app.services.knowledge.layout import SourceTable, ordered_blocks
from app.services.knowledge.pipeline import extract_knowledge, write_knowledge_json
from app.services.knowledge.persistence import persist_bundle
from app.services.knowledge.types import ExtractionBundle, SourceRef, VocabularyRecord
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


def test_appendix_pages_do_not_extend_final_lesson_but_transcripts_are_kept():
    raw = {
        "source": {"page_count": 3},
        "pages": [
            {
                "pdf_page_number": 1,
                "width": 600,
                "height": 800,
                "blocks": [{"index": 0, "text": "15 약속", "bbox": [50, 80, 200, 100]}],
                "tables": [],
            },
            {
                "pdf_page_number": 2,
                "width": 600,
                "height": 800,
                "blocks": [{"index": 0, "text": "15 약속", "bbox": [50, 80, 200, 100]}],
                "tables": [],
            },
            {
                "pdf_page_number": 3,
                "width": 600,
                "height": 800,
                "blocks": [
                    {"index": 0, "text": "듣기 대본", "bbox": [50, 30, 200, 50]},
                    {
                        "index": 1,
                        "text": "TRANSCRIPT[CD1TRACK01]: 안녕하세요.",
                        "bbox": [50, 80, 450, 100],
                    },
                    {"index": 2, "text": "15 약속", "bbox": [50, 120, 200, 140]},
                ],
                "tables": [],
            },
        ],
    }

    bundle = extract_knowledge(raw)

    assert [(item.ordinal, item.start_pdf_page, item.end_pdf_page) for item in bundle.lessons] == [
        (15, 1, 2)
    ]
    assert [transcript.source.pdf_page_number for transcript in bundle.transcripts] == [3]
    assert any("Excluded appendix pages from lesson segmentation: 3-3" in warning for warning in bundle.warnings)


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

        unresolved_bundle = ExtractionBundle(vocabulary=[
            VocabularyRecord(
                source=SourceRef(1, "1", block_index=999),
                headword="검증",
                normalized_headword="검증",
                meanings_vi=["kiểm chứng"],
            )
        ])
        unresolved_counts = persist_bundle(
            session, textbook.id, unresolved_bundle, source_document.id,
        )
        session.commit()
        assert unresolved_counts["unresolved_sources"] == 1
        assert any("Source span unresolved" in warning for warning in unresolved_bundle.warnings)
        assert session.scalar(select(func.count(Vocabulary.id))) == 0

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
        assert first_counts["exercise_options"] == 2
        assert first_counts["answers"] == 1
        assert second_counts["exercise_options"] == 0
        assert second_counts["answers"] == 0
        lesson_id = session.scalar(select(Lesson.id))
        client_session_book_id = textbook.id

    assert client.get(f"/api/v1/textbooks/{client_session_book_id}/lessons").status_code == 200
    assert client.get(f"/api/v1/lessons/{lesson_id}/vocabulary").json()[0]["meanings_vi"]
    assert client.get(f"/api/v1/lessons/{lesson_id}/grammar").json()[0]["source_page_number"] == 1
    assert client.get(f"/api/v1/lessons/{lesson_id}/sentences").status_code == 200
    assert client.get(f"/api/v1/lessons/{lesson_id}/reading").status_code == 200
    assert client.get(f"/api/v1/lessons/{lesson_id}/listening").json()[0]["audio_status"] == "missing"
    assert client.get(f"/api/v1/lessons/{lesson_id}/exercises").status_code == 200


def test_real_layout_bilingual_cells_glossary_and_grammar_are_extracted():
    from app.services.knowledge.grammar import extract_grammar
    from app.services.knowledge.layout import SourceBlock, SourceTable
    from app.services.knowledge.vocabulary import extract_vocabulary

    tables = [SourceTable(
        page_number=2,
        printed_page_number="1",
        table_index=0,
        bbox=(10, 10, 500, 200),
        rows=[["모자\ncái mũ", "신발\ngiày dép"]],
    )]
    blocks = [
        SourceBlock(3, "2", 0, "새 단어", (40, 100, 100, 120), 600, 800, False),
        SourceBlock(3, "2", 1, "정확하다", (50, 150, 120, 170), 600, 800, False),
        SourceBlock(3, "2", 2, "chính xác", (50, 172, 140, 190), 600, 800, False),
        SourceBlock(4, "3", 0, "-아/어 보다", (50, 50, 180, 70), 600, 800, False),
        SourceBlock(4, "3", 1, "Được dùng để diễn tả việc thử thực hiện một hành động.", (50, 80, 500, 110), 600, 800, False),
        SourceBlock(4, "3", 2, "이 옷을 입어 봐요.", (70, 180, 260, 200), 600, 800, False),
    ]

    vocabulary = extract_vocabulary(tables, blocks)
    assert [(item.headword, item.meanings_vi) for item in vocabulary] == [
        ("모자", ["cái mũ"]),
        ("신발", ["giày dép"]),
        ("정확하다", ["chính xác"]),
    ]
    grammar, sentences = extract_grammar(blocks)
    assert grammar[0].pattern == "-아/어 보다"
    assert grammar[0].explanation_vi is not None
    assert sentences[0].text_ko == "이 옷을 입어 봐요."
    assert grammar[0].example_ids == [sentences[0].local_id]


def test_real_layout_passages_dialogues_and_exercises_remain_source_linked():
    from app.services.knowledge.layout import SourceBlock
    from app.services.knowledge.real_layout import extract_real_layout

    def block(index: int, text: str, page: int = 10) -> SourceBlock:
        return SourceBlock(page, str(page - 1), index, text, (50, 50 + index * 20, 500, 70 + index * 20), 600, 800, False)

    blocks = [
        block(0, "말하기"),
        block(1, "A 안녕하세요."),
        block(2, "B 반갑습니다."),
        block(12, "Bài 01 19"),
        block(13, "."),
        block(3, "1 사진을 보고 이야기해 보십시오."),
        block(4, "읽기", 11),
        block(5, "한국어를 배우는 사람들은 여러 가지 방법으로 매일 연습합니다. " * 3, 11),
        block(6, "2 잘 읽고 질문에 답하십시오.", 11),
        block(7, "(1) 글의 중심 생각은 무엇입니까?", 11),
        block(8, "듣기", 12),
        block(9, "1 대화를 듣고 답하십시오. CD1 TRACK 02", 12),
        block(10, "(1) 들은 내용과 같은 것을 고르십시오. ⓐ 하나 ⓑ 둘", 12),
    ]
    dialogues, passages, exercises = extract_real_layout(blocks)
    assert [turn.speaker for turn in dialogues] == ["A", "B"]
    assert passages[0].source.pdf_page_number == 11
    assert any(item.parent_id for item in exercises)
    listening_question = next(item for item in exercises if item.listening_track_id and item.options)
    assert listening_question.listening_track_id == "CD1TRACK02"
    assert listening_question.options


def test_exercise_golden_fixture_distinguishes_groups_questions_options_and_answers():
    """The marker fixture is a public synthetic contract, not textbook text."""
    raw = {
        "source": {"page_count": 3},
        "pages": [
            {
                "pdf_page_number": 1,
                "width": 600,
                "height": 800,
                "blocks": [
                    {"index": 0, "text": "EXERCISE[mc]: multiple_choice || 알맞은 답을 고르세요", "bbox": [20, 20, 500, 40]},
                    {"index": 1, "text": "Q1: 빈칸에 알맞은 것을 고르세요.", "bbox": [20, 60, 500, 80]},
                    {"index": 2, "text": "① 하나", "bbox": [30, 100, 200, 120]},
                    {"index": 3, "text": "② 둘", "bbox": [30, 130, 200, 150]},
                    {"index": 4, "text": "③ 셋", "bbox": [30, 160, 200, 180]},
                    {"index": 5, "text": "④ 넷", "bbox": [30, 190, 200, 210]},
                    {"index": 6, "text": "EXERCISE[fill]: fill_blank || 빈칸을 완성하세요", "bbox": [20, 240, 500, 260]},
                    {"index": 7, "text": "Q1: 문장을 완성하세요.", "bbox": [20, 280, 500, 300]},
                    {"index": 8, "text": "EXERCISE[match]: matching || 알맞게 연결하세요", "bbox": [20, 330, 500, 350]},
                    {"index": 9, "text": "Q1: 단어와 뜻을 연결하세요.", "bbox": [20, 370, 500, 390]},
                    {"index": 10, "text": "EXERCISE[order]: ordering || 문장의 순서를 정하세요", "bbox": [20, 420, 500, 440]},
                    {"index": 11, "text": "Q1: 문장을 바르게 배열하세요.", "bbox": [20, 460, 500, 480]},
                    {"index": 12, "text": "EXERCISE[free]: short_answer || 질문에 답하세요", "bbox": [20, 510, 500, 530]},
                    {"index": 13, "text": "Q1: 어디에 갑니까?", "bbox": [20, 550, 500, 570]},
                    {"index": 14, "text": "EXERCISE[multi]: multiple_choice || 두 문제를 푸세요", "bbox": [20, 600, 500, 620]},
                    {"index": 15, "text": "Q1: 첫 번째 질문입니다.", "bbox": [20, 640, 500, 660]},
                    {"index": 16, "text": "Q2: 두 번째 질문입니다.", "bbox": [20, 680, 500, 700]},
                ],
                "tables": [],
            },
            {
                "pdf_page_number": 2,
                "width": 600,
                "height": 800,
                "blocks": [
                    {"index": 0, "text": "ANSWER[mc.q1]: ②", "bbox": [20, 20, 500, 40]},
                    {"index": 1, "text": "ANSWER[fill.q1]: 문장을 완성했습니다.", "bbox": [20, 60, 500, 80]},
                    {"index": 2, "text": "ANSWER[q1]: ambiguous", "bbox": [20, 100, 500, 120]},
                ],
                "tables": [],
            },
            {"pdf_page_number": 3, "width": 600, "height": 800, "blocks": [], "tables": []},
        ],
    }

    bundle = extract_knowledge(raw)
    groups = [item for item in bundle.exercises if item.parent_id is None]
    questions = [item for item in bundle.exercises if item.parent_id is not None]
    assert len(groups) == 6
    assert len(questions) == 7
    assert [item.local_id for item in questions] == [
        "mc.q1", "fill.q1", "match.q1", "order.q1", "free.q1", "multi.q1", "multi.q2",
    ]
    mc = next(item for item in questions if item.local_id == "mc.q1")
    assert mc.exercise_type == "multiple_choice"
    assert [(item.option_index, item.text) for item in mc.options] == [
        (1, "하나"), (2, "둘"), (3, "셋"), (4, "넷"),
    ]
    assert [item.source.block_index for item in mc.options] == [2, 3, 4, 5]
    assert mc.answer == "②"
    assert mc.answer_source is not None and mc.answer_source.pdf_page_number == 2
    assert next(item for item in questions if item.local_id == "fill.q1").answer == "문장을 완성했습니다."
    assert next(item for item in questions if item.local_id == "multi.q1").answer is None
    assert next(item for item in questions if item.local_id == "multi.q2").answer is None
    assert all(item.source.pdf_page_number in {1, 2} for item in bundle.exercises)
    assert not any("Answer not found for exercise" in warning for warning in bundle.warnings)
    assert any("Answer unresolved for question multi.q1" in warning for warning in bundle.warnings)


def test_real_layout_does_not_turn_group_instructions_into_questions():
    from app.services.knowledge.layout import SourceBlock
    from app.services.knowledge.real_layout import extract_real_layout

    def block(index: int, text: str) -> SourceBlock:
        return SourceBlock(20, "19", index, text, (40, 50 + index * 25, 560, 70 + index * 25), 600, 800, False)

    _, _, exercises = extract_real_layout([
        block(0, "듣기"),
        block(1, "1 대화를 듣고 알맞은 답을 고르십시오. CD1 TRACK 02"),
        block(2, "(1) 들은 내용과 같은 것을 고르십시오. ① 하나 ② 둘"),
        block(3, "(2) 들은 내용과 다른 것을 고르십시오."),
        block(4, "① 보기 하나"),
        block(5, "② 보기 둘"),
        block(6, "2 다음 문장을 읽고 질문에 답하십시오."),
        block(7, "(1) 중심 생각은 무엇입니까?"),
    ])
    groups = [item for item in exercises if item.parent_id is None]
    questions = [item for item in exercises if item.parent_id is not None]
    assert len(groups) == 2
    assert len(questions) == 3
    assert groups[0].prompt.startswith("1 대화를 듣고")
    assert questions[0].exercise_type == "multiple_choice"
    assert [option.option_index for option in questions[0].options] == [1, 2]
    assert questions[0].listening_track_id == "CD1TRACK02"
    assert [item.local_id for item in questions] == [
        "LISTENING-P20-G1.q1", "LISTENING-P20-G1.q2", "LISTENING-P20-G2.q1",
    ]


def test_learner_api_never_grades_without_approved_answer_or_incomplete_options(client):
    with database.SessionLocal() as session:
        textbook = Textbook(owner_id="test-owner", title="Exercise safety", level="test", volume_number=91)
        session.add(textbook)
        session.flush()
        lesson = Lesson(
            textbook_id=textbook.id, ordinal=1, title="Exercises",
            start_pdf_page=1, end_pdf_page=1, segmentation_method="fixture",
            review_status="approved",
        )
        session.add(lesson)
        session.flush()
        incomplete = Exercise(
            lesson_id=lesson.id, prompt="Incomplete choice", exercise_type="multiple_choice",
            review_status="approved", group_identifier="incomplete",
        )
        no_answer = Exercise(
            lesson_id=lesson.id, prompt="Choice without sourced answer", exercise_type="multiple_choice",
            review_status="approved", group_identifier="no-answer",
        )
        session.add_all([incomplete, no_answer])
        session.flush()
        session.add_all([
            ExerciseOption(
                exercise_id=incomplete.id, option_index=1, text="A", review_status="approved",
            ),
            ExerciseOption(
                exercise_id=no_answer.id, option_index=1, text="A", review_status="approved",
            ),
            ExerciseOption(
                exercise_id=no_answer.id, option_index=2, text="B", review_status="approved",
            ),
        ])
        session.commit()
        lesson_id = lesson.id
        incomplete_id = incomplete.id
        no_answer_id = no_answer.id

    approved_feed = client.get(f"/api/v1/lessons/{lesson_id}/exercises?review_status=approved")
    assert approved_feed.status_code == 200
    assert [item["id"] for item in approved_feed.json()] == [no_answer_id]
    attempt = client.post(
        f"/api/v1/study/exercises/{no_answer_id}/attempt",
        json={"answer": "A"},
    )
    assert attempt.status_code == 200
    assert attempt.json()["correct"] is None
    assert attempt.json()["answer_revealed"] is None
    incomplete_attempt = client.post(
        f"/api/v1/study/exercises/{incomplete_id}/attempt",
        json={"answer": "A"},
    )
    assert incomplete_attempt.status_code == 409
