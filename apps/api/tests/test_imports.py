import pytest


from pathlib import Path


def test_import_is_idempotent_for_same_pdf_bytes(client, tmp_path):
    fitz = pytest.importorskip("fitz")
    source = tmp_path / "lesson.pdf"
    document = fitz.open()
    document.new_page()
    document.save(source)
    document.close()
    payload = {
        "source_path": str(source),
        "title": "Source fixture",
        "level": "beginner",
        "volume_number": 1,
    }
    first = client.post("/api/v1/imports", json=payload)
    second = client.post("/api/v1/imports", json=payload)
    assert first.status_code == 202
    assert second.status_code == 202
    assert first.json()["already_imported"] is False
    assert second.json()["already_imported"] is True
    assert first.json()["source_document_id"] == second.json()["source_document_id"]

    from app.models import SourceDocument
    from app.database import SessionLocal
    with SessionLocal() as session:
        document = session.get(SourceDocument, first.json()["source_document_id"])
        assert document.owner_id == "test-owner"
        assert document.rights_status == "unverified"
        assert Path(document.source_path).is_file()
        assert "private" in Path(document.source_path).parts


def test_private_endpoints_require_authentication(client):
    client.headers.pop("Authorization")
    response = client.get("/api/v1/textbooks")
    assert response.status_code == 401


def test_extraction_requires_explicit_authorized_rights(client, tmp_path):
    import fitz

    def make_pdf(path: Path, text: str) -> None:
        pdf = fitz.open()
        page = pdf.new_page()
        page.insert_text((72, 72), text)
        pdf.save(path)
        pdf.close()

    unverified_path = tmp_path / "unverified.pdf"
    make_pdf(unverified_path, "unverified fixture")
    unverified = client.post("/api/v1/imports", json={
        "source_path": str(unverified_path),
        "title": "Fixture",
        "level": "beginner",
        "volume_number": 1,
    }).json()
    assert client.post(f"/api/v1/imports/{unverified['job_id']}/queue").status_code == 403

    authorized_path = tmp_path / "authorized.pdf"
    make_pdf(authorized_path, "authorized fixture")
    authorized = client.post("/api/v1/imports", json={
        "source_path": str(authorized_path),
        "title": "Fixture",
        "level": "beginner",
        "volume_number": 1,
        "rights_status": "authorized",
    }).json()
    queued = client.post(f"/api/v1/imports/{authorized['job_id']}/queue")
    assert queued.status_code == 200
    assert queued.json()["state"] == "queued"


def test_owner_can_delete_private_source_and_document_records(client, tmp_path):
    import fitz

    source = tmp_path / "delete-me.pdf"
    document = fitz.open()
    document.new_page()
    document.save(source)
    document.close()
    response = client.post("/api/v1/imports", json={
        "source_path": str(source),
        "title": "Fixture",
        "level": "beginner",
        "volume_number": 1,
    })
    document_id = response.json()["source_document_id"]
    from app.database import SessionLocal
    from app.models import (
        AnswerKey,
        ContentProvenance,
        ContentReview,
        Dialogue,
        DialogueTurn,
        Exercise,
        ExerciseOption,
        GrammarPattern,
        Lesson,
        LessonSection,
        ListeningTrack,
        Passage,
        Sentence,
        SourceBlock,
        SourceDocument,
        SourcePage,
        SourceSpan,
        Transcript,
        Vocabulary,
        WordSense,
    )
    with SessionLocal() as session:
        source_document = session.get(SourceDocument, document_id)
        private_path = Path(source_document.source_path)
        assert private_path.exists()
        page = SourcePage(
            source_document_id=document_id,
            pdf_page_number=1,
            raw_text="synthetic",
        )
        session.add(page)
        session.flush()
        block = SourceBlock(
            source_page_id=page.id, block_index=0, text="synthetic",
            x0=0, y0=0, x1=100, y1=20,
        )
        session.add(block)
        session.flush()
        span = SourceSpan(
            source_page_id=page.id, source_block_id=block.id, label="raw_block",
            raw_text="synthetic", normalized_text="synthetic",
        )
        lesson = Lesson(
            textbook_id=source_document.textbook_id, ordinal=1, title="Fixture lesson",
            start_pdf_page=1, end_pdf_page=1, segmentation_method="fixture",
        )
        session.add_all([span, lesson])
        session.flush()
        vocabulary = Vocabulary(
            lesson_id=lesson.id, headword="단어", normalized_headword="단어",
            extraction_method="fixture", source_span_id=span.id,
        )
        grammar = GrammarPattern(
            lesson_id=lesson.id, pattern="-어요", normalized_pattern="-어요",
            extraction_method="fixture", source_span_id=span.id,
        )
        passage = Passage(
            lesson_id=lesson.id, title="Reading", text="text", source_span_id=span.id,
        )
        track = ListeningTrack(
            lesson_id=lesson.id, source_span_id=span.id, track_identifier="CD1TRACK01",
        )
        dialogue = Dialogue(lesson_id=lesson.id, source_span_id=span.id, group_identifier="d1")
        session.add_all([vocabulary, grammar, passage, track, dialogue])
        session.flush()
        sense = WordSense(vocabulary_id=vocabulary.id, meaning_vi="word", source_span_id=span.id)
        sentence = Sentence(
            lesson_id=lesson.id, text_ko="문장", text_vi="Câu",
            source_span_id=span.id, vocabulary_items=[vocabulary], grammar_patterns=[grammar],
        )
        section = LessonSection(
            lesson_id=lesson.id, section_type="reading", title="Reading",
            source_span_id=span.id, source_page_number=1,
        )
        parent = Exercise(
            lesson_id=lesson.id, prompt="group", source_span_id=span.id,
            passage_id=passage.id, listening_track_id=track.id,
        )
        session.add_all([sense, sentence, section, parent])
        session.flush()
        child = Exercise(
            lesson_id=lesson.id, prompt="question", source_span_id=span.id,
            parent_exercise_id=parent.id, passage_id=passage.id,
        )
        session.add(child)
        session.flush()
        session.add_all([
            ExerciseOption(exercise_id=child.id, option_index=1, text="option", source_span_id=span.id),
            AnswerKey(exercise_id=child.id, answer_text="A", source_span_id=span.id),
            Transcript(listening_track_id=track.id, text="transcript", source_span_id=span.id),
            DialogueTurn(dialogue_id=dialogue.id, turn_index=0, text="turn", source_span_id=span.id),
            ContentProvenance(
                entity_type="vocabulary", entity_id=vocabulary.id,
                source_span_id=span.id, extraction_method="fixture",
            ),
            ContentReview(entity_type="vocabulary", entity_id=vocabulary.id, status="approved"),
        ])
        session.commit()

    deleted = client.delete(f"/api/v1/imports/documents/{document_id}")
    assert deleted.status_code == 200
    assert not private_path.exists()
    assert client.get("/api/v1/imports/1").status_code == 404
    with SessionLocal() as session:
        for model in (
            AnswerKey, ContentProvenance, ContentReview, Dialogue, DialogueTurn,
            Exercise, ExerciseOption, GrammarPattern, Lesson, LessonSection,
            ListeningTrack, Passage, Sentence, SourceBlock, SourcePage,
            SourceSpan, Transcript, Vocabulary, WordSense,
        ):
            assert session.query(model).count() == 0
