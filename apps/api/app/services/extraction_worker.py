"""Database-backed extraction worker. Run separately from document registration."""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.models import ImportJob, ImportState, Lesson, SourceBlock, SourceDocument, SourcePage, SourceSpan
from app.services.pdf_engine import PdfValidationError, extract_pages
from app.services.segmentation import DEFAULT_PROFILE, detect_lesson_boundaries, normalize_text


def queue_job(session: Session, job: ImportJob) -> ImportJob:
    if job.state in {ImportState.registered, ImportState.failed} and job.attempts < job.max_attempts:
        job.state = ImportState.queued
        job.message = "Queued for deterministic PDF extraction."
        session.commit()
        session.refresh(job)
    return job


def run_job(session: Session, job: ImportJob) -> ImportJob:
    if job.state != ImportState.queued:
        return job
    document = session.get(SourceDocument, job.source_document_id)
    if document is None:
        job.state = ImportState.failed
        job.message = "Source document no longer exists."
        session.commit()
        return job
    job.state = ImportState.extracting
    job.attempts += 1
    job.message = "Extracting page-level raw content."
    session.commit()
    try:
        pages = extract_pages(document.source_path)
        session.execute(delete(SourcePage).where(SourcePage.source_document_id == document.id))
        session.flush()
        page_text: dict[int, str] = {}
        for raw_page in pages:
            page = SourcePage(
                source_document_id=document.id,
                pdf_page_number=raw_page.pdf_page_number,
                printed_page_number=raw_page.printed_page_number,
                raw_text=raw_page.text,
                korean_character_count=raw_page.korean_character_count,
                vietnamese_character_count=raw_page.vietnamese_character_count,
                image_count=raw_page.image_count,
                needs_ocr=raw_page.needs_ocr,
            )
            session.add(page)
            session.flush()
            page_text[raw_page.pdf_page_number] = raw_page.text
            for block in raw_page.blocks:
                persisted = SourceBlock(source_page_id=page.id, block_index=block.index, text=block.text, x0=block.x0, y0=block.y0, x1=block.x1, y1=block.y1, is_header_footer_candidate=block.is_header_footer_candidate)
                session.add(persisted)
                session.flush()
                if block.text:
                    session.add(SourceSpan(source_page_id=page.id, source_block_id=persisted.id, label="raw_block", raw_text=block.text, normalized_text=normalize_text(block.text), confidence=1.0, review_status="not_required"))
        textbook_id = document.textbook_id
        session.execute(delete(Lesson).where(Lesson.textbook_id == textbook_id))
        for boundary in detect_lesson_boundaries(page_text, DEFAULT_PROFILE):
            session.add(Lesson(textbook_id=textbook_id, ordinal=boundary.ordinal, title=boundary.title, start_pdf_page=boundary.pdf_page_number, segmentation_method=DEFAULT_PROFILE.name, review_status="pending"))
        job.state = ImportState.extracted
        job.message = "Raw pages and provisional lesson boundaries extracted. Structured records await review/extractors."
    except (PdfValidationError, RuntimeError, OSError) as error:
        job.state = ImportState.failed
        job.message = str(error)
    finally:
        session.commit()
        session.refresh(job)
    return job


def run_next_job(session: Session) -> ImportJob | None:
    job = session.scalar(select(ImportJob).where(ImportJob.state == ImportState.queued).order_by(ImportJob.created_at))
    return run_job(session, job) if job else None
