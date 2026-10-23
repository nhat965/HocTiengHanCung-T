import json


def _seed_knowledge():
    from app.database import SessionLocal
    from app.models import (
        Dialogue, DialogueTurn, Lesson, Sentence, Textbook, Vocabulary, WordSense,
    )

    with SessionLocal() as session:
        textbook = Textbook(
            owner_id="test-owner", title="Licensed fixture", level="beginner", volume_number=1,
        )
        session.add(textbook)
        session.flush()
        lesson = Lesson(
            textbook_id=textbook.id, ordinal=1, title="첫 수업",
            start_pdf_page=1, end_pdf_page=1, segmentation_method="fixture",
        )
        session.add(lesson)
        session.flush()
        vocabulary = Vocabulary(
            lesson_id=lesson.id, headword="사과", normalized_headword="사과",
            extraction_method="fixture", review_status="pending",
        )
        sentence = Sentence(
            lesson_id=lesson.id, text_ko="사과를 먹어요.", text_vi="Tôi ăn táo.",
            review_status="approved",
        )
        dialogue = Dialogue(lesson_id=lesson.id, group_identifier="dlg-1", topic="인사")
        session.add_all([vocabulary, sentence, dialogue])
        session.flush()
        session.add_all([
            WordSense(vocabulary_id=vocabulary.id, meaning_vi="quả táo"),
            DialogueTurn(
                dialogue_id=dialogue.id, turn_index=0, speaker="가",
                text="안녕하세요.", text_vi="Xin chào.", review_status="approved",
            ),
        ])
        session.commit()
        return textbook.id, lesson.id, vocabulary.id


def test_review_workflow_and_owner_scoped_exports(client):
    textbook_id, lesson_id, vocabulary_id = _seed_knowledge()

    queued = client.get("/api/v1/review?review_status=pending")
    assert queued.status_code == 200
    assert any(item["entity_type"] == "vocabulary" and item["entity_id"] == vocabulary_id for item in queued.json())

    reviewed = client.post(
        f"/api/v1/review/vocabulary/{vocabulary_id}",
        json={"status": "approved", "note": "Compared with licensed fixture."},
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
