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


def test_same_pdf_supports_distinct_overlapping_ranges_and_retry(
    client, tmp_path, monkeypatch,
):
    """A file is shared by jobs, while each job owns one extraction range."""
    import fitz

    from app import database
    from app.models import ImportJob, ImportState, SourceDocument, SourcePage
    from app.services import extraction_worker

    source = tmp_path / "multi-range.pdf"
    pdf = fitz.open()
    for page_number in range(1, 54):
        page = pdf.new_page()
        page.insert_text((72, 72), f"Fixture page {page_number}")
    pdf.save(source)
    pdf.close()

    def register(start: int, end: int) -> dict:
        response = client.post("/api/v1/imports", json={
            "source_path": str(source),
            "title": "Multi-range fixture",
            "level": "intermediate",
            "volume_number": 4,
            "rights_status": "authorized",
            "page_start": start,
            "page_end": end,
        })
        assert response.status_code == 202, response.text
        return response.json()

    first = register(18, 35)
    second = register(36, 53)
    overlap = register(30, 40)
    same_first = register(18, 35)

    assert first["already_imported"] is False
    assert second["already_imported"] is False
    assert overlap["already_imported"] is False
    assert same_first["already_imported"] is True
    assert first["source_document_id"] == second["source_document_id"] == overlap["source_document_id"]
    assert len({first["job_id"], second["job_id"], overlap["job_id"]}) == 3

    for registration in (first, second):
        queued = client.post(f"/api/v1/imports/{registration['job_id']}/queue")
        assert queued.status_code == 200, queued.text

    with database.SessionLocal() as session:
        document = session.get(SourceDocument, first["source_document_id"])
        assert document is not None
        assert document.page_start is None and document.page_end is None
        results = [extraction_worker.run_next_job(session) for _ in range(2)]
        assert all(result is not None and result.state == ImportState.needs_review for result in results)
        assert {
            (result.page_start, result.page_end)
            for result in results
        } == {(18, 35), (36, 53)}
        pages = list(session.query(SourcePage).order_by(SourcePage.pdf_page_number))
        assert len(pages) == 36
        assert [page.pdf_page_number for page in pages] == list(range(18, 54))

    same_after_success = register(18, 35)
    assert same_after_success["already_imported"] is True
    assert same_after_success["job_id"] == first["job_id"]

    queued_overlap = client.post(f"/api/v1/imports/{overlap['job_id']}/queue")
    assert queued_overlap.status_code == 200, queued_overlap.text

    original_extract_pages = extraction_worker.extract_pages

    def fail_once(*args, **kwargs):
        raise RuntimeError("temporary fixture failure")

    monkeypatch.setattr(extraction_worker, "extract_pages", fail_once)
    with database.SessionLocal() as session:
        failed = extraction_worker.run_next_job(session)
        assert failed is not None
        assert failed.state == ImportState.failed
        assert failed.failure_stage == "raw_extraction"

    monkeypatch.setattr(extraction_worker, "extract_pages", original_extract_pages)
    retry = client.post(f"/api/v1/imports/{overlap['job_id']}/queue")
    assert retry.status_code == 200
    with database.SessionLocal() as session:
        completed = extraction_worker.run_next_job(session)
        assert completed is not None
        assert completed.state == ImportState.needs_review
        assert completed.page_start == 30
        assert completed.page_end == 40
        assert session.query(SourcePage).count() == 36


def test_delete_document_is_blocked_while_worker_is_active(client, tmp_path):
    import fitz
    from datetime import datetime, timedelta

    from app.database import SessionLocal
    from app.models import ImportJob, ImportState

    source = tmp_path / "active-worker.pdf"
    pdf = fitz.open()
    pdf.new_page()
    pdf.save(source)
    pdf.close()
    registered = client.post("/api/v1/imports", json={
        "source_path": str(source), "title": "Active worker", "level": "beginner",
        "volume_number": 5, "rights_status": "authorized",
    }).json()
    document_id = registered["source_document_id"]
    with SessionLocal() as session:
        job = session.get(ImportJob, registered["job_id"])
        job.state = ImportState.extracting
        job.worker_token = "active-worker-token"
        job.lease_expires_at = datetime.utcnow() + timedelta(minutes=30)
        session.commit()

    response = client.delete(f"/api/v1/imports/documents/{document_id}")
    assert response.status_code == 409


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
    from app.database import SessionLocal
    from app.models import ImportJob, ImportState, SourcePage
    from app.services.extraction_worker import run_job
    with SessionLocal() as session:
        job = session.get(ImportJob, unverified["job_id"])
        job.state = ImportState.queued
        session.commit()
        result = run_job(session, job)
        assert result.state == ImportState.failed
        assert result.failure_stage == "rights_check"
        assert session.query(SourcePage).count() == 0

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


def test_knowledge_reads_are_scoped_to_authenticated_owner(client):
    from app.database import SessionLocal
    from app.models import Lesson, Textbook

    with SessionLocal() as session:
        textbook = Textbook(
            owner_id="different-owner",
            title="Private to another owner",
            level="beginner",
            volume_number=6,
        )
        session.add(textbook)
        session.flush()
        lesson = Lesson(
            textbook_id=textbook.id,
            ordinal=1,
            title="Private lesson",
            start_pdf_page=1,
            end_pdf_page=1,
            segmentation_method="fixture",
        )
        session.add(lesson)
        session.commit()
        textbook_id = textbook.id
        lesson_id = lesson.id

    assert all(item["id"] != textbook_id for item in client.get("/api/v1/textbooks").json())
    assert client.get(f"/api/v1/textbooks/{textbook_id}/lessons").status_code == 404
    assert client.get(f"/api/v1/lessons/{lesson_id}").status_code == 404
