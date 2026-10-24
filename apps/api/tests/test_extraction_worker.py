import hashlib
import os
from pathlib import Path

import fitz
import pytest
from sqlalchemy import func, select, update

from app import database
from app.models import (
    AnswerKey,
    ContentProvenance,
    Dialogue,
    DialogueTurn,
    Exercise,
    ExerciseOption,
    GrammarNote,
    GrammarPattern,
    ImportJob,
    ImportState,
    Lesson,
    LessonProgress,
    ListeningTrack,
    Passage,
    Sentence,
    SentenceIdentity,
    StudyAttempt,
    SourceBlock,
    SourceDocument,
    SourcePage,
    SourceSpan,
    Textbook,
    Transcript,
    Vocabulary,
    VocabularyProgress,
    WordSense,
)
from app.services import extraction_worker
from app.services.extraction_worker import recover_stale_jobs, run_job, run_next_job


def _korean_font() -> Path | None:
    candidates = [
        Path(os.environ.get("WINDIR", "C:/Windows")) / "Fonts" / "malgun.ttf",
        Path("/usr/share/fonts/truetype/unfonts-core/UnDotum.ttf"),
        Path("/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc"),
        Path("/usr/share/fonts/truetype/noto/NotoSansCJK-Regular.ttc"),
    ]
    return next((path for path in candidates if path.is_file()), None)


def _vietnamese_font() -> Path | None:
    candidates = [
        Path(os.environ.get("WINDIR", "C:/Windows")) / "Fonts" / "arial.ttf",
        Path("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"),
        Path("/usr/share/fonts/truetype/liberation2/LiberationSans-Regular.ttf"),
        Path("/usr/share/fonts/truetype/noto/NotoSans-Regular.ttf"),
    ]
    return next((path for path in candidates if path.is_file()), None)


def _write_structured_fixture(path: Path) -> None:
    font_path = _korean_font()
    vietnamese_font_path = _vietnamese_font()
    if font_path is None or vietnamese_font_path is None:
        pytest.skip("Korean and Vietnamese fonts are required for the real PDF extraction fixture")
    pdf = fitz.open()
    page = pdf.new_page()
    page.insert_font(fontname="korean", fontfile=str(font_path))
    page.insert_font(fontname="vietnamese", fontfile=str(vietnamese_font_path))
    korean_font = fitz.Font(fontfile=str(font_path))
    vietnamese_font = fitz.Font(fontfile=str(vietnamese_font_path))
    content = [
        ("01 유행", True),
        ("Fixture NUL: before\x00after", False),
        ("GRAMMAR: -아/어 보다 || thử làm", True),
        ("EXAMPLE: 책을 읽어 봐요. || Tôi thử đọc sách.", True),
        ("DIALOGUE[dlg1]: At a cafe", False),
        ("민수: 커피 주세요. || Cho tôi cà phê.", True),
        ("영희: 여기 있습니다. || Đây ạ.", True),
        ("READING[read1]: A short story", False),
        ("PARAGRAPH: first paragraph", False),
        ("PARAGRAPH: second paragraph", False),
        ("EXERCISE[grp1]: multiple_choice || Choose an answer", False),
        ("Q1: Choose the correct answer", False),
        ("OPTION: A", False),
        ("OPTION: B", False),
        ("CD1 TRACK 01", False),
        ("TRANSCRIPT[CD1TRACK01]: synthetic transcript", False),
        ("ANSWER[grp1.q1]: A", False),
    ]
    for index, (line, korean) in enumerate(content):
        baseline = 130 + index * 34
        if korean and " || " in line:
            korean_text, vietnamese_text = line.split(" || ", maxsplit=1)
            prefix = korean_text + " || "
            writer = fitz.TextWriter(page.rect)
            writer.append(
                fitz.Point(55, baseline), prefix,
                font=korean_font, fontsize=11,
            )
            x = 55 + korean_font.text_length(prefix, fontsize=11)
            writer.append(
                fitz.Point(x, baseline), vietnamese_text,
                font=vietnamese_font, fontsize=11,
            )
            writer.write_text(page)
        else:
            page.insert_text(
                (55, baseline),
                line,
                fontname="korean" if korean else "helv",
                fontsize=11,
            )
    for x in (50, 300, 550):
        page.draw_line((x, 700), (x, 800), color=(0, 0, 0), width=1)
    for y in (700, 730, 760, 800):
        page.draw_line((50, y), (550, y), color=(0, 0, 0), width=1)
    page.insert_text((60, 722), "사과", fontname="korean", fontsize=11)
    page.insert_text((310, 722), "quả táo", fontname="vietnamese", fontsize=11)
    page.insert_text((60, 752), "가다", fontname="korean", fontsize=11)
    page.insert_text((310, 752), "đi", fontname="vietnamese", fontsize=11)
    page.insert_text((310, 782), "NUL table cell: before\x00after", fontsize=9)
    pdf.save(path)
    pdf.close()


def test_registered_fixture_runs_through_database_api_retry_and_delete(client, tmp_path, monkeypatch):
    fixture = tmp_path / "authorized-fixture.pdf"
    _write_structured_fixture(fixture)
    registration = client.post("/api/v1/imports", json={
        "source_path": str(fixture),
        "title": "Synthetic fixture",
        "level": "intermediate",
        "volume_number": 4,
        "rights_status": "authorized",
    })
    assert registration.status_code == 202
    document_id = registration.json()["source_document_id"]
    job_id = registration.json()["job_id"]
    assert client.post(f"/api/v1/imports/{job_id}/queue").status_code == 200

    persist = extraction_worker.persist_bundle

    def fail_after_structured_flush(session, *args, **kwargs):
        counts = persist(session, *args, **kwargs)
        assert counts["grammar"] == 1
        raise RuntimeError("synthetic transaction failure")

    monkeypatch.setattr(extraction_worker, "persist_bundle", fail_after_structured_flush)
    with database.SessionLocal() as session:
        failed = run_next_job(session)
        assert failed is not None
        assert failed.state == ImportState.failed
        assert failed.failure_stage == "structured_persistence"
        assert failed.stage == "failed"
        assert failed.attempts == 1
        assert session.scalar(select(func.count(SourcePage.id)).where(
            SourcePage.source_document_id == document_id,
        )) == 1
        assert session.scalar(select(func.count(GrammarPattern.id))) == 0

    monkeypatch.setattr(extraction_worker, "persist_bundle", persist)
    assert client.post(f"/api/v1/imports/{job_id}/queue").status_code == 200
    with database.SessionLocal() as session:
        completed = run_next_job(session)
        assert completed is not None
        assert completed.state == ImportState.needs_review
        assert completed.stage == "complete"
        assert completed.failure_stage is None
        assert completed.record_counts["grammar"] == 1
        assert completed.record_counts["vocabulary"] == 2
        assert completed.record_counts["sentences"] == 1
        assert completed.record_counts["passages"] == 1
        assert completed.record_counts["exercises"] == 2
        assert completed.record_counts["listening_tracks"] == 1
        assert completed.quality_summary["text_sanitization"]["nul_replacements"] > 0
        source_page = session.scalar(select(SourcePage).where(
            SourcePage.source_document_id == document_id,
        ))
        assert source_page is not None
        assert "\uFFFD" in source_page.raw_text
        assert "\x00" not in source_page.raw_text
        assert all("\x00" not in block.text for block in session.scalars(
            select(SourceBlock).where(SourceBlock.source_page_id == source_page.id),
        ))
        source_spans = list(session.scalars(
            select(SourceSpan).where(SourceSpan.source_page_id == source_page.id),
        ))
        assert all("\x00" not in span.raw_text for span in source_spans)
        assert any(span.label.startswith("raw_table:") for span in source_spans)
        assert any(
            span.label.startswith("raw_table:") and "\uFFFD" in span.raw_text
            for span in source_spans
        )
        textbook = session.get(Textbook, source_page.source_document.textbook_id)
        assert textbook is not None
        textbook.title = "Fixture\x00 title"
        persisted_job = session.get(ImportJob, job_id)
        assert persisted_job is not None
        persisted_quality = dict(persisted_job.quality_summary)
        persisted_quality["sanitizer_probe"] = {"value": "한국어\x00 tiếng Việt"}
        persisted_job.quality_summary = persisted_quality
        session.commit()
        session.refresh(textbook)
        session.refresh(persisted_job)
        assert textbook.title == "Fixture\uFFFD title"
        assert persisted_job.quality_summary["sanitizer_probe"]["value"] == "한국어\uFFFD tiếng Việt"
        grammar = session.scalar(select(GrammarPattern))
        assert grammar is not None
        grammar.pattern = "reviewed grammar"
        grammar.review_status = "approved"
        session.commit()

    lesson_response = client.get(f"/api/v1/textbooks/{client.get('/api/v1/textbooks').json()[0]['id']}/lessons")
    assert lesson_response.status_code == 200
    lesson_id = lesson_response.json()[0]["id"]
    assert client.get(f"/api/v1/lessons/{lesson_id}/grammar").json()[0]["pattern"] == "reviewed grammar"
    assert len(client.get(f"/api/v1/lessons/{lesson_id}/vocabulary").json()) == 2
    assert len(client.get(f"/api/v1/lessons/{lesson_id}/sentences").json()) == 1
    assert len(client.get(f"/api/v1/lessons/{lesson_id}/reading").json()) == 1
    assert len(client.get(f"/api/v1/lessons/{lesson_id}/exercises").json()) == 2
    listening = client.get(f"/api/v1/lessons/{lesson_id}/listening").json()
    assert listening[0]["transcript_available"] is True
    status_response = client.get(f"/api/v1/imports/{job_id}")
    assert status_response.json()["stage"] == "complete"
    quality = client.get(f"/api/v1/imports/{job_id}/report").json()
    assert quality["quality"]["structural_counts"]["grammar_patterns"] == 1

    second_registration = client.post("/api/v1/imports", json={
        "source_path": str(fixture),
        "title": "Synthetic fixture",
        "level": "intermediate",
        "volume_number": 4,
        "rights_status": "authorized",
    })
    assert second_registration.json()["already_imported"] is True
    assert client.post(f"/api/v1/imports/{job_id}/queue").status_code == 200
    with database.SessionLocal() as session:
        rerun = run_next_job(session)
        assert rerun is not None and rerun.state == ImportState.needs_review
        assert session.scalar(select(func.count(Lesson.id))) == 1
        assert session.scalar(select(func.count(GrammarPattern.id))) == 1
        assert session.scalar(select(func.count(Vocabulary.id))) == 2
        assert session.scalar(select(func.count(Sentence.id))) == 1
        assert session.scalar(select(func.count(SentenceIdentity.id))) == 1
        assert session.scalar(select(Sentence.identity_id)) is not None
        assert session.scalar(select(func.count(Passage.id))) == 1
        assert session.scalar(select(func.count(ContentProvenance.id))) > 0
        assert session.scalar(select(GrammarPattern)).pattern == "reviewed grammar"

    deletion = client.delete(f"/api/v1/imports/documents/{document_id}")
    assert deletion.status_code == 200
    with database.SessionLocal() as session:
        for model in (
            ContentProvenance, Dialogue, DialogueTurn, GrammarPattern, Lesson, Passage, Sentence, SentenceIdentity,
            SourceBlock, SourcePage, SourceSpan, Vocabulary,
        ):
            assert session.scalar(select(func.count(model.id))) == 0


def test_fixture_supports_private_learning_journey(client, tmp_path):
    fixture = tmp_path / "learning-fixture.pdf"
    _write_structured_fixture(fixture)
    registered = client.post("/api/v1/imports", json={
        "source_path": str(fixture),
        "title": "Synthetic learning fixture",
        "level": "intermediate",
        "volume_number": 4,
        "rights_status": "authorized",
    })
    assert registered.status_code == 202
    document_id = registered.json()["source_document_id"]
    job_id = registered.json()["job_id"]
    assert client.post(f"/api/v1/imports/{job_id}/queue").status_code == 200
    with database.SessionLocal() as session:
        result = run_next_job(session)
        assert result is not None and result.state == ImportState.needs_review
        assert result.record_counts["lessons"] == 1
        assert result.record_counts["vocabulary"] == 2
        assert result.record_counts["word_senses"] == 2
        assert result.record_counts["grammar"] == 1
        assert result.record_counts["sentences"] == 1
        assert result.record_counts["dialogue_turns"] == 2
        assert result.record_counts["passages"] == 1
        assert result.record_counts["exercises"] == 2
        assert result.record_counts["exercise_options"] == 2
        assert result.record_counts["answers"] == 1
        assert result.record_counts["listening_tracks"] == 1
        assert result.record_counts["transcripts"] == 1
        lesson_id = session.scalar(select(Lesson.id))
        assert lesson_id is not None
    assert client.get(f"/api/v1/lessons/{lesson_id}/dialogues").json() == []

    models_by_entity = {
        "vocabulary": Vocabulary,
        "word_sense": WordSense,
        "dialogue_turn": DialogueTurn,
        "grammar": GrammarPattern,
        "sentence": Sentence,
        "passage": Passage,
        "exercise": Exercise,
        "exercise_option": ExerciseOption,
        "answer_key": AnswerKey,
        "listening_track": ListeningTrack,
        "transcript": Transcript,
    }
    approvals = []
    with database.SessionLocal() as session:
        for entity_type, model in models_by_entity.items():
            for record in session.scalars(select(model)).all():
                source_span_id = session.scalar(select(ContentProvenance.source_span_id).where(
                    ContentProvenance.entity_type == entity_type,
                    ContentProvenance.entity_id == record.id,
                ).order_by(ContentProvenance.id))
                if source_span_id is not None:
                    approvals.append((entity_type, record.id, record.version, source_span_id))
    assert approvals
    for entity_type, entity_id, version, source_span_id in approvals:
        response = client.post(f"/api/v1/review/{entity_type}/{entity_id}", json={
            "status": "approved",
            "expected_version": version,
            "source_span_id": source_span_id,
            "reviewer_action": "compared_to_source",
            "checks": ["source_text", "source_position"],
        })
        assert response.status_code == 200, response.text

    books = client.get("/api/v1/textbooks").json()
    assert len(books) == 1
    assert books[0]["data_status"] == "ready"
    assert books[0]["lesson_count"] == 1
    lessons = client.get(f"/api/v1/textbooks/{books[0]['id']}/lessons").json()
    assert len(lessons) == 1 and lessons[0]["id"] == lesson_id
    assert lessons[0]["vocabulary_count"] == 2
    assert lessons[0]["grammar_count"] == 1

    exercise_response = client.get(
        f"/api/v1/lessons/{lesson_id}/exercises?review_status=approved"
    )
    assert exercise_response.status_code == 200
    exercises = exercise_response.json()
    assert len(exercises) == 2
    assert sum(item["has_children"] for item in exercises) == 1
    assert all("parent_exercise_id" in item for item in exercises)
    assert all("answer_revealed" not in item and "answer_key" not in item for item in exercises)
    dialogues = client.get(f"/api/v1/lessons/{lesson_id}/dialogues").json()
    assert len(dialogues) == 1 and len(dialogues[0]["turns"]) == 2
    flashcards = client.get(f"/api/v1/study/lessons/{lesson_id}/flashcards").json()
    assert len(flashcards) == 2
    assert {
        card["headword"]: card["meanings_vi"]
        for card in flashcards
    } == {"사과": ["quả táo"], "가다": ["đi"]}

    first_card = flashcards[0]
    learned = client.post(f"/api/v1/study/vocabulary/{first_card['vocabulary_id']}/learned")
    assert learned.status_code == 200 and learned.json()["status"] == "learned"

    with database.SessionLocal() as session:
        grammar_id = session.scalar(select(GrammarPattern.id))
    assert grammar_id is not None
    note = client.post(f"/api/v1/study/grammar/{grammar_id}/note", json={"note": "Ôn lại cấu trúc này"})
    assert note.status_code == 200
    assert client.get(f"/api/v1/study/grammar/{grammar_id}/note").json()["note"] == "Ôn lại cấu trúc này"

    choice_exercise = next(item for item in exercises if item["options"])
    submitted = client.post(
        f"/api/v1/study/exercises/{choice_exercise['id']}/attempt",
        json={"answer": "A"},
    )
    assert submitted.status_code == 200
    assert submitted.json()["correct"] is True
    assert submitted.json()["answer_revealed"] == "A"

    assert client.post(f"/api/v1/study/lessons/{lesson_id}/open").status_code == 200
    assert client.post(f"/api/v1/study/lessons/{lesson_id}/complete").status_code == 200
    persisted_progress = client.get("/api/v1/study/progress").json()
    refreshed_progress = client.get("/api/v1/study/progress").json()
    assert persisted_progress == refreshed_progress
    assert refreshed_progress["learned_vocabulary"] == 1
    assert refreshed_progress["attempts"] == 1
    assert refreshed_progress["completed_lessons"] == 1
    assert client.get(f"/api/v1/textbooks/{books[0]['id']}/lessons").json()[0]["progress_status"] == "completed"
    quality = client.get(f"/api/v1/imports/{job_id}/report")
    assert quality.status_code == 200
    assert quality.json()["quality"]["structural_counts"]["vocabulary"] == 2
    assert quality.json()["quality"]["structural_counts"]["grammar_patterns"] == 1
    assert quality.json()["raw_extraction"]["accuracy_note"].startswith(
        "Accuracy is intentionally not estimated"
    )

    assert client.delete(f"/api/v1/imports/documents/{document_id}").status_code == 200
    with database.SessionLocal() as session:
        for model in (
            AnswerKey, ContentProvenance, Dialogue, DialogueTurn, Exercise, ExerciseOption, GrammarNote,
            GrammarPattern, Lesson, LessonProgress, ListeningTrack, Passage,
            Sentence, StudyAttempt, Transcript, Vocabulary, VocabularyProgress,
            WordSense,
        ):
            assert session.scalar(select(func.count(model.id))) == 0


def test_stale_worker_jobs_are_requeued_or_failed_at_retry_limit(client):
    from datetime import datetime, timedelta

    with database.SessionLocal() as session:
        textbook = Textbook(owner_id="test-owner", title="Fixture", level="beginner", volume_number=1)
        session.add(textbook)
        session.flush()
        document = SourceDocument(
            owner_id="test-owner",
            textbook_id=textbook.id,
            filename="fixture.pdf",
            sha256="a" * 64,
            source_path="private/fixture.pdf",
            rights_status="authorized",
        )
        session.add(document)
        session.flush()
        recoverable = ImportJob(
            source_document_id=document.id,
            state=ImportState.extracting,
            stage="structured_persistence",
            attempts=1,
            max_attempts=3,
        )
        exhausted = ImportJob(
            source_document_id=document.id,
            state=ImportState.extracting,
            stage="raw_extraction",
            attempts=3,
            max_attempts=3,
        )
        session.add_all([recoverable, exhausted])
        session.flush()
        stale_time = datetime.utcnow() - timedelta(hours=2)
        session.commit()
        session.execute(
            update(ImportJob)
            .where(ImportJob.id.in_([recoverable.id, exhausted.id]))
            .values(updated_at=stale_time)
        )
        session.commit()

        assert recover_stale_jobs(session) == 2
        assert session.get(ImportJob, recoverable.id).state == ImportState.queued
        assert session.get(ImportJob, recoverable.id).failure_stage == "structured_persistence"
        assert session.get(ImportJob, exhausted.id).state == ImportState.failed
        assert session.get(ImportJob, exhausted.id).failure_stage == "raw_extraction"


def test_reimport_is_idempotent_and_preserves_reviewed_records(client, tmp_path: Path):
    pdf_path = tmp_path / "worker-source.pdf"
    pdf = fitz.open()
    page = pdf.new_page()
    page.insert_text((72, 72), "Original source text")
    pdf.save(pdf_path)
    pdf.close()
    digest = hashlib.sha256(pdf_path.read_bytes()).hexdigest()

    with database.SessionLocal() as session:
        textbook = Textbook(title="Fixture", level="intermediate", volume_number=4)
        session.add(textbook)
        session.flush()
        source = SourceDocument(
            textbook_id=textbook.id,
            filename=pdf_path.name,
            sha256=digest,
            page_count=1,
            source_path=str(pdf_path),
            rights_status="authorized",
        )
        session.add(source)
        session.flush()
        job = ImportJob(source_document_id=source.id, state=ImportState.queued, message="queued")
        existing_page = SourcePage(
            source_document_id=source.id,
            pdf_page_number=1,
            raw_text="old extraction",
        )
        session.add_all([job, existing_page])
        session.flush()
        existing_block = SourceBlock(
            source_page_id=existing_page.id,
            block_index=0,
            text="old extraction",
            x0=0,
            y0=0,
            x1=10,
            y1=10,
            is_header_footer_candidate=False,
        )
        existing_lesson = Lesson(
            textbook_id=textbook.id,
            ordinal=1,
            title="Reviewed title",
            start_pdf_page=1,
            segmentation_method="human-reviewed",
            review_status="approved",
        )
        session.add_all([existing_block, existing_lesson])
        session.flush()
        reviewed_span = SourceSpan(
            source_page_id=existing_page.id,
            source_block_id=existing_block.id,
            label="raw_block",
            raw_text="old extraction",
            normalized_text="old extraction",
            confidence=0.6,
            review_status="approved",
        )
        session.add(reviewed_span)
        session.commit()

        result = run_job(session, job)
        assert result.state == ImportState.needs_review
        assert result.stage == "complete"
        assert session.scalar(select(func.count(SourcePage.id))) == 1
        assert session.scalar(select(func.count(SourceBlock.id))) == 1
        assert session.scalar(select(func.count(SourceSpan.id))) == 1
        assert session.scalar(select(func.count(Lesson.id))) == 1
        assert session.get(Lesson, existing_lesson.id).title == "Reviewed title"
        assert session.get(Lesson, existing_lesson.id).review_status == "approved"
        assert session.get(SourceSpan, reviewed_span.id).review_status == "approved"
        assert session.get(SourceSpan, reviewed_span.id).confidence == 0.6
        assert session.get(SourceSpan, reviewed_span.id).raw_text == "old extraction"

        result.state = ImportState.queued
        session.commit()
        result = run_job(session, result)
        assert result.state == ImportState.needs_review
        assert result.stage == "complete"
        assert session.scalar(select(func.count(SourcePage.id))) == 1
        assert session.scalar(select(func.count(SourceBlock.id))) == 1
        assert session.scalar(select(func.count(SourceSpan.id))) == 1
        assert session.scalar(select(func.count(Lesson.id))) == 1

        pdf_path.write_bytes(b"changed after registration")
        result.state = ImportState.queued
        session.commit()
        result = run_job(session, result)
        assert result.state == ImportState.failed
        assert result.failure_stage == "raw_extraction"
        assert "validation failed" in result.message
        assert session.get(SourceSpan, reviewed_span.id).review_status == "approved"


def test_reimport_preserves_approved_knowledge_and_learning_state(client, tmp_path: Path):
    """A full re-extraction must preserve reviewed content and learner state."""
    from app.models import ContentReview

    def snapshot(row):
        return {
            key: value
            for key, value in row.__dict__.items()
            if not key.startswith("_")
        }

    fixture = tmp_path / "preservation-fixture.pdf"
    _write_structured_fixture(fixture)
    registered = client.post("/api/v1/imports", json={
        "source_path": str(fixture),
        "title": "Preservation fixture",
        "level": "intermediate",
        "volume_number": 4,
        "rights_status": "authorized",
    })
    assert registered.status_code == 202
    document_id = registered.json()["source_document_id"]
    job_id = registered.json()["job_id"]
    assert client.post(f"/api/v1/imports/{job_id}/queue").status_code == 200
    with database.SessionLocal() as session:
        result = run_next_job(session)
        assert result is not None and result.state == ImportState.needs_review
        lesson_id = session.scalar(select(Lesson.id))
        vocabulary = session.scalar(select(Vocabulary).order_by(Vocabulary.id))
        sense = session.scalar(select(WordSense).where(WordSense.vocabulary_id == vocabulary.id))
        grammar = session.scalar(select(GrammarPattern).order_by(GrammarPattern.id))
        exercise = session.scalar(select(Exercise).order_by(Exercise.id.desc()))
        assert lesson_id and vocabulary and sense and grammar and exercise
        record_ids = {
            "lesson": lesson_id,
            "vocabulary": vocabulary.id,
            "sense": sense.id,
            "grammar": grammar.id,
            "exercise": exercise.id,
        }
        provenance = {
            key: session.scalar(select(ContentProvenance.source_span_id).where(
                ContentProvenance.entity_type == entity_type,
                ContentProvenance.entity_id == entity_id,
            ).order_by(ContentProvenance.id))
            for key, entity_type, entity_id in (
                ("vocabulary", "vocabulary", vocabulary.id),
                ("sense", "word_sense", sense.id),
                ("grammar", "grammar", grammar.id),
                ("exercise", "exercise", exercise.id),
            )
        }
        assert all(provenance.values())

    for entity_type in ("vocabulary", "word_sense", "grammar", "exercise"):
        entity_key = "sense" if entity_type == "word_sense" else entity_type
        with database.SessionLocal() as session:
            model = {
                "vocabulary": Vocabulary,
                "word_sense": WordSense,
                "grammar": GrammarPattern,
                "exercise": Exercise,
            }[entity_type]
            record = session.get(model, record_ids[entity_key])
            version = record.version
        response = client.post(f"/api/v1/review/{entity_type}/{record.id}", json={
            "status": "approved",
            "expected_version": version,
            "source_span_id": provenance[entity_key],
            "reviewer_action": "compared_to_source",
            "checks": ["source_text", "source_position"],
        })
        assert response.status_code == 200, response.text

    with database.SessionLocal() as session:
        sense = session.get(WordSense, record_ids["sense"])
        sense.meaning_vi = "nghĩa đã sửa thủ công"
        session.commit()

    assert client.post(
        f"/api/v1/study/grammar/{record_ids['grammar']}/note",
        json={"note": "Ghi chú cá nhân cần giữ nguyên"},
    ).status_code == 200
    assert client.post(f"/api/v1/study/vocabulary/{record_ids['vocabulary']}/learned").status_code == 200
    assert client.post(f"/api/v1/study/lessons/{record_ids['lesson']}/complete").status_code == 200

    with database.SessionLocal() as session:
        option = session.scalar(select(ExerciseOption).where(
            ExerciseOption.exercise_id == record_ids["exercise"],
        ).order_by(ExerciseOption.option_index))
        assert option is not None
        option_id = option.id
    attempt = client.post(
        f"/api/v1/study/exercises/{record_ids['exercise']}/attempt",
        json={"answer": "A"},
    )
    assert attempt.status_code == 200, attempt.text

    with database.SessionLocal() as session:
        before = {
            "vocabulary": snapshot(session.get(Vocabulary, record_ids["vocabulary"])),
            "sense": snapshot(session.get(WordSense, record_ids["sense"])),
            "grammar": snapshot(session.get(GrammarPattern, record_ids["grammar"])),
            "lesson": snapshot(session.get(Lesson, record_ids["lesson"])),
            "exercise": snapshot(session.get(Exercise, record_ids["exercise"])),
            "progress": snapshot(session.scalar(select(VocabularyProgress).where(
                VocabularyProgress.vocabulary_id == record_ids["vocabulary"],
            ))),
            "lesson_progress": snapshot(session.scalar(select(LessonProgress).where(
                LessonProgress.lesson_id == record_ids["lesson"],
            ))),
            "note": snapshot(session.scalar(select(GrammarNote).where(
                GrammarNote.grammar_pattern_id == record_ids["grammar"],
            ))),
            "attempts": [snapshot(row) for row in session.scalars(select(StudyAttempt).order_by(StudyAttempt.id)).all()],
            "reviews": session.scalar(select(func.count(ContentReview.id))),
            "provenance": {
                key: session.scalar(select(ContentProvenance.source_span_id).where(
                    ContentProvenance.entity_type == entity_type,
                    ContentProvenance.entity_id == entity_id,
                ).order_by(ContentProvenance.id))
                for key, entity_type, entity_id in (
                    ("vocabulary", "vocabulary", record_ids["vocabulary"]),
                    ("sense", "word_sense", record_ids["sense"]),
                    ("grammar", "grammar", record_ids["grammar"]),
                    ("exercise", "exercise", record_ids["exercise"]),
                )
            },
            "option_id": option_id,
        }
        job = session.get(ImportJob, job_id)
        job.state = ImportState.queued
        session.commit()
        rerun = run_job(session, job)
        assert rerun.state == ImportState.needs_review

    with database.SessionLocal() as session:
        after = {
            "vocabulary": snapshot(session.get(Vocabulary, record_ids["vocabulary"])),
            "sense": snapshot(session.get(WordSense, record_ids["sense"])),
            "grammar": snapshot(session.get(GrammarPattern, record_ids["grammar"])),
            "lesson": snapshot(session.get(Lesson, record_ids["lesson"])),
            "exercise": snapshot(session.get(Exercise, record_ids["exercise"])),
            "progress": snapshot(session.scalar(select(VocabularyProgress).where(
                VocabularyProgress.vocabulary_id == record_ids["vocabulary"],
            ))),
            "lesson_progress": snapshot(session.scalar(select(LessonProgress).where(
                LessonProgress.lesson_id == record_ids["lesson"],
            ))),
            "note": snapshot(session.scalar(select(GrammarNote).where(
                GrammarNote.grammar_pattern_id == record_ids["grammar"],
            ))),
            "attempts": [snapshot(row) for row in session.scalars(select(StudyAttempt).order_by(StudyAttempt.id)).all()],
            "reviews": session.scalar(select(func.count(ContentReview.id))),
            "provenance": {
                key: session.scalar(select(ContentProvenance.source_span_id).where(
                    ContentProvenance.entity_type == entity_type,
                    ContentProvenance.entity_id == entity_id,
                ).order_by(ContentProvenance.id))
                for key, entity_type, entity_id in (
                    ("vocabulary", "vocabulary", record_ids["vocabulary"]),
                    ("sense", "word_sense", record_ids["sense"]),
                    ("grammar", "grammar", record_ids["grammar"]),
                    ("exercise", "exercise", record_ids["exercise"]),
                )
            },
        }
        for key in ("vocabulary", "sense", "grammar", "lesson", "exercise"):
            for field in ("id", "review_status", "version"):
                    assert after[key][field] == before[key][field], f"{key}.{field}: {before[key][field]} -> {after[key][field]}"
        assert after["sense"]["meaning_vi"] == before["sense"]["meaning_vi"]
        assert after["progress"] == before["progress"]
        assert after["lesson_progress"] == before["lesson_progress"]
        assert after["note"] == before["note"]
        assert after["attempts"] == before["attempts"]
        assert after["reviews"] == before["reviews"]
        assert after["provenance"] == before["provenance"]
        assert session.scalar(select(func.count(Vocabulary.id))) == 2
        assert session.scalar(select(func.count(GrammarPattern.id))) == 1
        assert session.scalar(select(func.count(Exercise.id))) == 2, [
            (row.id, row.group_identifier, row.prompt, row.parent_exercise_id)
            for row in session.scalars(select(Exercise).order_by(Exercise.id)).all()
        ]
        assert session.scalar(select(func.count(ExerciseOption.id))) == 2
