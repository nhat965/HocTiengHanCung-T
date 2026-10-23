import hashlib
import json
import os
from pathlib import Path

import fitz
import pytest
from sqlalchemy import func, select, update

from app import database
from app.models import (
    ContentProvenance,
    GrammarPattern,
    ImportJob,
    ImportState,
    Lesson,
    Passage,
    Sentence,
    SourceBlock,
    SourceDocument,
    SourcePage,
    SourceSpan,
    Textbook,
    Vocabulary,
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


def _write_structured_fixture(path: Path) -> None:
    font_path = _korean_font()
    if font_path is None:
        pytest.skip("A Korean font is required to generate a real PDF extraction fixture")
    pdf = fitz.open()
    page = pdf.new_page()
    page.insert_font(fontname="korean", fontfile=str(font_path))
    content = [
        ("01 유행", True),
        ("GRAMMAR: -아/어 보다 || thử làm", True),
        ("EXAMPLE: 책을 읽어 봐요. || Tôi thử đọc sách.", True),
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
        page.insert_text(
            (55, 130 + index * 34),
            line,
            fontname="korean" if korean else "helv",
            fontsize=11,
        )
    for x in (50, 300, 550):
        page.draw_line((x, 600), (x, 700), color=(0, 0, 0), width=1)
    for y in (600, 630, 660, 700):
        page.draw_line((50, y), (550, y), color=(0, 0, 0), width=1)
    page.insert_text((60, 622), "사과", fontname="korean", fontsize=11)
    page.insert_text((310, 622), "quả táo", fontsize=11)
    page.insert_text((60, 652), "가다", fontname="korean", fontsize=11)
    page.insert_text((310, 652), "đi", fontsize=11)
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
    failure_diagnostics = {}
    record_failure = extraction_worker._fail

    def capture_failure(session, job_id, stage, message, error):
        if stage == "raw_persistence":
            original_error = getattr(error, "orig", error)
            diagnostic = getattr(original_error, "diag", None)
            failure_diagnostics.update({
                "error": type(error).__name__,
                "cause": type(original_error).__name__,
                "sqlstate": (
                    getattr(original_error, "sqlstate", None)
                    or getattr(original_error, "pgcode", None)
                ),
                "message_primary": getattr(diagnostic, "message_primary", None),
                "table_name": getattr(diagnostic, "table_name", None),
                "column_name": getattr(diagnostic, "column_name", None),
                "datatype_name": getattr(diagnostic, "datatype_name", None),
                "statement": getattr(error, "statement", None),
            })
            print(f"Sanitized PostgreSQL failure metadata: {json.dumps(failure_diagnostics)}")
        return record_failure(session, job_id, stage, message, error)

    monkeypatch.setattr(extraction_worker, "_fail", capture_failure)
    with database.SessionLocal() as session:
        failed = run_next_job(session)
        assert failed is not None
        assert failed.state == ImportState.failed
        assert failed.failure_stage == "structured_persistence", failed.message
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
        assert session.scalar(select(func.count(Passage.id))) == 1
        assert session.scalar(select(func.count(ContentProvenance.id))) > 0
        assert session.scalar(select(GrammarPattern)).pattern == "reviewed grammar"

    deletion = client.delete(f"/api/v1/imports/documents/{document_id}")
    assert deletion.status_code == 200
    with database.SessionLocal() as session:
        for model in (
            ContentProvenance, GrammarPattern, Lesson, Passage, Sentence,
            SourceBlock, SourcePage, SourceSpan, Vocabulary,
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
