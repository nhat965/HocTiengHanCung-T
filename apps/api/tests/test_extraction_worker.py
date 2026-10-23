import hashlib
from pathlib import Path

import fitz
from sqlalchemy import func, select

from app import database
from app.models import (
    ImportJob,
    ImportState,
    Lesson,
    SourceBlock,
    SourceDocument,
    SourcePage,
    SourceSpan,
    Textbook,
)
from app.services.extraction_worker import run_job


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
        assert result.state == ImportState.extracted
        assert session.scalar(select(func.count(SourcePage.id))) == 1
        assert session.scalar(select(func.count(SourceBlock.id))) == 1
        assert session.scalar(select(func.count(SourceSpan.id))) == 1
        assert session.scalar(select(func.count(Lesson.id))) == 1
        assert session.get(Lesson, existing_lesson.id).title == "Reviewed title"
        assert session.get(Lesson, existing_lesson.id).review_status == "approved"
        assert session.get(SourceSpan, reviewed_span.id).review_status == "approved"
        assert session.get(SourceSpan, reviewed_span.id).confidence == 0.6

        result.state = ImportState.queued
        session.commit()
        result = run_job(session, result)
        assert result.state == ImportState.extracted
        assert session.scalar(select(func.count(SourcePage.id))) == 1
        assert session.scalar(select(func.count(SourceBlock.id))) == 1
        assert session.scalar(select(func.count(SourceSpan.id))) == 1
        assert session.scalar(select(func.count(Lesson.id))) == 1

        pdf_path.write_bytes(b"changed after registration")
        result.state = ImportState.queued
        session.commit()
        result = run_job(session, result)
        assert result.state == ImportState.failed
        assert "changed after registration" in result.message
        assert session.get(SourceSpan, reviewed_span.id).review_status == "approved"
