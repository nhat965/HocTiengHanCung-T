"""Database-backed extraction worker. Run separately from document registration."""
from __future__ import annotations

import logging
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import ImportJob, ImportState, Lesson, SourceBlock, SourceDocument, SourcePage, SourceSpan
from app.services.pdf_engine import PdfValidationError, extract_pages
from app.services.pdf_importer import sha256_file
from app.services.segmentation import DEFAULT_PROFILE, detect_lesson_boundaries, normalize_text

logger = logging.getLogger(__name__)


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
    if document.rights_status != "authorized":
        job.state = ImportState.failed
        job.message = "Document rights must be marked authorized before extraction."
        session.commit()
        return job
    document_path = Path(document.source_path)
    document_id = document.id
    textbook_id = document.textbook_id
    document_sha256 = document.sha256
    job.state = ImportState.extracting
    job.attempts += 1
    job.message = "Extracting page-level raw content."
    session.commit()
    try:
        if sha256_file(document_path) != document_sha256:
            raise PdfValidationError("Source PDF changed after registration; register it again to extract the new bytes")
        pages = extract_pages(document_path)
        page_text: dict[int, str] = {}
        with session.begin():
            existing_pages = {
                page.pdf_page_number: page
                for page in session.scalars(
                    select(SourcePage).where(SourcePage.source_document_id == document_id)
                ).all()
            }
            for raw_page in pages:
                page = existing_pages.get(raw_page.pdf_page_number)
                if page is None:
                    page = SourcePage(
                        source_document_id=document_id,
                        pdf_page_number=raw_page.pdf_page_number,
                        raw_text=raw_page.text,
                        korean_character_count=raw_page.korean_character_count,
                        vietnamese_character_count=raw_page.vietnamese_character_count,
                        image_count=raw_page.image_count,
                        needs_ocr=raw_page.needs_ocr,
                    )
                    session.add(page)
                    session.flush()
                else:
                    page.printed_page_number = raw_page.printed_page_number
                    page.raw_text = raw_page.text
                    page.korean_character_count = raw_page.korean_character_count
                    page.vietnamese_character_count = raw_page.vietnamese_character_count
                    page.image_count = raw_page.image_count
                    page.needs_ocr = raw_page.needs_ocr
                page_text[raw_page.pdf_page_number] = raw_page.text

                existing_blocks = {
                    block.block_index: block
                    for block in session.scalars(
                        select(SourceBlock).where(SourceBlock.source_page_id == page.id)
                    ).all()
                }
                for block in raw_page.blocks:
                    persisted = existing_blocks.get(block.index)
                    if persisted is None:
                        persisted = SourceBlock(
                            source_page_id=page.id,
                            block_index=block.index,
                            text=block.text,
                            x0=block.x0,
                            y0=block.y0,
                            x1=block.x1,
                            y1=block.y1,
                            is_header_footer_candidate=block.is_header_footer_candidate,
                        )
                        session.add(persisted)
                        session.flush()
                    else:
                        persisted.text = block.text
                        persisted.x0 = block.x0
                        persisted.y0 = block.y0
                        persisted.x1 = block.x1
                        persisted.y1 = block.y1
                        persisted.is_header_footer_candidate = block.is_header_footer_candidate
                    if block.text:
                        source_span = session.scalar(
                            select(SourceSpan).where(
                                SourceSpan.source_block_id == persisted.id,
                                SourceSpan.label == "raw_block",
                            )
                        )
                        if source_span is None:
                            session.add(SourceSpan(
                                source_page_id=page.id,
                                source_block_id=persisted.id,
                                label="raw_block",
                                raw_text=block.text,
                                normalized_text=normalize_text(block.text),
                                confidence=0.0,
                                review_status="pending",
                            ))
                        elif source_span.review_status not in {"approved", "reviewed"}:
                            source_span.raw_text = block.text
                            source_span.normalized_text = normalize_text(block.text)
                for table in raw_page.tables:
                    for row_index, row in enumerate(table.rows):
                        raw_row = " | ".join(cell or "" for cell in row).strip()
                        if not raw_row:
                            continue
                        label = f"raw_table:{table.index}:{row_index}"
                        source_span = session.scalar(select(SourceSpan).where(
                            SourceSpan.source_page_id == page.id,
                            SourceSpan.label == label,
                        ))
                        if source_span is None:
                            session.add(SourceSpan(
                                source_page_id=page.id,
                                label=label,
                                raw_text=raw_row,
                                normalized_text=normalize_text(raw_row),
                                confidence=0.0,
                                review_status="pending",
                            ))
                        elif source_span.review_status not in {"approved", "reviewed"}:
                            source_span.raw_text = raw_row
                            source_span.normalized_text = normalize_text(raw_row)

            existing_lessons = {
                (lesson.ordinal, lesson.start_pdf_page)
                for lesson in session.scalars(
                    select(Lesson).where(Lesson.textbook_id == textbook_id)
                ).all()
            }
            for boundary in detect_lesson_boundaries(page_text, DEFAULT_PROFILE):
                key = (boundary.ordinal, boundary.pdf_page_number)
                if key not in existing_lessons:
                    session.add(Lesson(
                        textbook_id=textbook_id,
                        ordinal=boundary.ordinal,
                        title=boundary.title,
                        start_pdf_page=boundary.pdf_page_number,
                        segmentation_method=DEFAULT_PROFILE.name,
                        review_status="pending",
                    ))
                    existing_lessons.add(key)
            job.state = ImportState.extracted
            job.message = "Raw pages and provisional lesson boundaries extracted. Structured records await review/extractors."
    except (PdfValidationError, RuntimeError, OSError) as error:
        session.rollback()
        job = session.get(ImportJob, job.id)
        job.state = ImportState.failed
        job.message = str(error)
        session.commit()
        session.refresh(job)
        return job
    except Exception:
        session.rollback()
        job = session.get(ImportJob, job.id)
        job.state = ImportState.failed
        job.message = "Unexpected extraction failure; see worker logs."
        session.commit()
        logger.exception("Unexpected PDF extraction failure for job %s", job.id)
        raise
    session.refresh(job)
    return job


def run_next_job(session: Session) -> ImportJob | None:
    job = session.scalar(select(ImportJob).where(ImportJob.state == ImportState.queued).order_by(ImportJob.created_at))
    return run_job(session, job) if job else None
