import json


def _seed_knowledge():
    from app.database import SessionLocal
    from app.models import (
        ContentProvenance, Dialogue, DialogueTurn, Lesson, Sentence, SourceDocument,
        SourcePage, SourceSpan, Textbook, Vocabulary, WordSense,
    )

    with SessionLocal() as session:
        textbook = Textbook(
            owner_id="test-owner", title="Licensed fixture", level="beginner", volume_number=1,
        )
        session.add(textbook)
        session.flush()
        document = SourceDocument(
            owner_id="test-owner", textbook_id=textbook.id, filename="fixture.pdf",
            sha256="a" * 64, page_count=1, source_path="fixture.pdf",
            rights_status="authorized",
        )
        session.add(document)
        session.flush()
        page = SourcePage(source_document_id=document.id, pdf_page_number=1, raw_text="사과 quả táo")
        session.add(page)
        session.flush()
        span = SourceSpan(
            source_page_id=page.id, label="fixture", raw_text="사과 quả táo",
            normalized_text="사과 quả táo", confidence=1.0,
        )
        session.add(span)
        session.flush()
        lesson = Lesson(
            textbook_id=textbook.id, ordinal=1, title="첫 수업",
            start_pdf_page=1, end_pdf_page=1, segmentation_method="fixture",
        )
        session.add(lesson)
        session.flush()
        vocabulary = Vocabulary(
            lesson_id=lesson.id, headword="사과", normalized_headword="사과",
            extraction_method="fixture", review_status="pending", source_span_id=span.id,
        )
        sentence = Sentence(
            lesson_id=lesson.id, text_ko="사과를 먹어요.", text_vi="Tôi ăn táo.",
            review_status="approved",
        )
        dialogue = Dialogue(lesson_id=lesson.id, group_identifier="dlg-1", topic="인사")
        session.add_all([vocabulary, sentence, dialogue])
        session.flush()
        session.add_all([
            WordSense(
                vocabulary_id=vocabulary.id, meaning_vi="quả táo",
                source_span_id=span.id, review_status="approved",
            ),
            ContentProvenance(
                entity_type="vocabulary", entity_id=vocabulary.id,
                source_span_id=span.id, extraction_method="fixture",
                extraction_version="structured-v1",
            ),
            DialogueTurn(
                dialogue_id=dialogue.id, turn_index=0, speaker="가",
                text="안녕하세요.", text_vi="Xin chào.", review_status="approved",
            ),
        ])
        session.commit()
        return textbook.id, lesson.id, vocabulary.id, span.id


def test_review_workflow_and_owner_scoped_exports(client):
    textbook_id, lesson_id, vocabulary_id, span_id = _seed_knowledge()

    queued = client.get("/api/v1/review?review_status=pending")
    assert queued.status_code == 200
    assert any(item["entity_type"] == "vocabulary" and item["entity_id"] == vocabulary_id for item in queued.json())

    incomplete_approval = client.post(
        f"/api/v1/review/vocabulary/{vocabulary_id}", json={"status": "approved"},
    )
    assert incomplete_approval.status_code == 409

    reviewed = client.post(
        f"/api/v1/review/vocabulary/{vocabulary_id}",
        json={
            "status": "approved", "note": "Compared with licensed fixture.",
            "expected_version": 1, "source_span_id": span_id,
            "reviewer_action": "compared_to_source",
            "checks": ["source_text", "source_position", "semantic_alignment"],
        },
    )
    assert reviewed.status_code == 200
    assert reviewed.json()["review_status"] == "approved"

    exported = client.get(f"/api/v1/textbooks/{textbook_id}/exports/vocabulary")
    assert exported.status_code == 200
    body = exported.json()
    assert body["metadata"]["schema_version"] == "1.0"
    assert body["metadata"]["review_status"] == "approved"
    assert body["metadata"]["record_count"] == 1
    assert body["records"][0]["meanings_vi"] == ["quả táo"]

    csv_export = client.get(f"/api/v1/textbooks/{textbook_id}/exports/vocabulary?format=csv")
    assert csv_export.status_code == 200
    assert "schema_version,source_identifier,extraction_version" in csv_export.text
    assert "사과" in csv_export.text

    jsonl = client.get(f"/api/v1/textbooks/{textbook_id}/exports/sentences?format=jsonl")
    lines = jsonl.text.strip().splitlines()
    assert json.loads(lines[0])["metadata"]["dataset"] == "sentences"
    assert json.loads(lines[1])["text_ko"] == "사과를 먹어요."

    dialogues = client.get(f"/api/v1/lessons/{lesson_id}/dialogues")
    assert dialogues.status_code == 200
    assert dialogues.json()[0]["turns"][0]["speaker"] == "가"

    cards = client.get(f"/api/v1/study/lessons/{lesson_id}/flashcards")
    assert cards.status_code == 200
    assert cards.json()[0]["meanings_vi"] == ["quả táo"]
    attempt = client.post(
        f"/api/v1/study/vocabulary/{vocabulary_id}/review",
        json={"answer_vi": "quả táo"},
    )
    assert attempt.status_code == 200
    assert attempt.json()["correct"] is True
    progress = client.get("/api/v1/study/progress").json()
    assert progress["approved_vocabulary"] == 1
    assert progress["attempts"] == 1


def test_review_and_export_reject_cross_owner_access(client):
    from app.database import SessionLocal
    from app.models import Lesson, Textbook, Vocabulary

    with SessionLocal() as session:
        textbook = Textbook(owner_id="other-owner", title="Other", level="advanced", volume_number=6)
        session.add(textbook)
        session.flush()
        lesson = Lesson(
            textbook_id=textbook.id, ordinal=1, title="Private", start_pdf_page=1,
            segmentation_method="fixture",
        )
        session.add(lesson)
        session.flush()
        vocabulary = Vocabulary(
            lesson_id=lesson.id, headword="비밀", normalized_headword="비밀",
            extraction_method="fixture",
        )
        session.add(vocabulary)
        session.commit()
        textbook_id = textbook.id
        vocabulary_id = vocabulary.id

    assert client.get(f"/api/v1/textbooks/{textbook_id}/exports/vocabulary").status_code == 404
    assert client.post(
        f"/api/v1/review/vocabulary/{vocabulary_id}", json={"status": "approved"},
    ).status_code == 404
