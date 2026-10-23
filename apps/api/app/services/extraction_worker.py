"""Database-backed raw and structured PDF extraction worker."""
from __future__ import annotations

from datetime import datetime, timedelta
import logging
from pathlib import Path
from typing import Any

from sqlalchemy import select, update
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.models import ImportJob, ImportState, Lesson, SourceBlock, SourceDocument, SourcePage, SourceSpan
from app.services.knowledge.persistence import persist_bundle
from app.services.knowledge.pipeline import extract_knowledge
from app.services.knowledge.quality import report_dict
from app.services.pdf_engine import PdfValidationError, RawPage, extract_pages
from app.services.pdf_importer import sha256_file
from app.services.segmentation import DEFAULT_PROFILE, detect_lesson_boundaries, normalize_text

logger = logging.getLogger(__name__)
STALE_JOB_TIMEOUT = timedelta(minutes=60)


def queue_job(session: Session, job: ImportJob) -> ImportJob:
    if job.state in {
        ImportState.registered,
        ImportState.failed,
        ImportState.extracted,
        ImportState.needs_review,
    } and job.attempts < job.max_attempts:
        job.state = ImportState.queued
        job.stage = "queued"
        job.failure_stage = None
        job.message = "Queued for raw and structured extraction."
        session.commit()
        session.refresh(job)
    return job


def _set_stage(session: Session, job_id: int, stage: str, message: str) -> ImportJob:
    job = session.get(ImportJob, job_id)
    if job is None:
        raise RuntimeError("Import job disappeared while running")
    job.state = ImportState.extracting
    job.stage = stage
    job.failure_stage = None
    job.message = message
    session.commit()
    return job


def _fail(session: Session, job_id: int, stage: str, message: str, error: Exception) -> ImportJob:
    session.rollback()
    job = session.get(ImportJob, job_id)
    if job is None:
        raise RuntimeError("Import job disappeared while recording failure") from error
    job.state = ImportState.failed
    job.stage = "failed"
    job.failure_stage = stage
    job.message = message
    session.commit()
    session.refresh(job)
    logger.error("Import job %s failed at stage %s (%s)", job_id, stage, type(error).__name__)
    return job


def _raw_document(source: SourceDocument, pages: list[RawPage]) -> dict[str, Any]:
    return {
        "schema_version": 1,
        "source": {
            "filename": source.filename,
            "sha256": source.sha256,
            "page_count": source.page_count or len(pages),
        },
        "pages": [
            {
                "pdf_page_number": page.pdf_page_number,
                "printed_page_number": page.printed_page_number,
                "width": page.width,
                "height": page.height,
                "rotation": page.rotation,
                "text": page.text,
                "blocks": [
                    {
                        "index": block.index,
                        "text": block.text,
                        "bbox": [block.x0, block.y0, block.x1, block.y1],
                        "is_header_footer_candidate": block.is_header_footer_candidate,
                    }
                    for block in page.blocks
                ],
                "tables": [
                    {
                        "index": table.index,
                        "bbox": [table.x0, table.y0, table.x1, table.y1],
                        "rows": table.rows,
                    }
                    for table in page.tables
                ],
            }
            for page in pages
        ],
    }


def _persist_raw_pages(
    session: Session,
    document_id: int,
    textbook_id: int,
    pages: list[RawPage],
) -> None:
    page_text: dict[int, str] = {}
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
        for raw_block in raw_page.blocks:
            block = existing_blocks.get(raw_block.index)
            if block is None:
                block = SourceBlock(
                    source_page_id=page.id,
                    block_index=raw_block.index,
                    text=raw_block.text,
                    x0=raw_block.x0,
                    y0=raw_block.y0,
                    x1=raw_block.x1,
                    y1=raw_block.y1,
                    is_header_footer_candidate=raw_block.is_header_footer_candidate,
                )
                session.add(block)
                session.flush()
            else:
                block.text = raw_block.text
                block.x0 = raw_block.x0
                block.y0 = raw_block.y0
                block.x1 = raw_block.x1
                block.y1 = raw_block.y1
                block.is_header_footer_candidate = raw_block.is_header_footer_candidate
            if not raw_block.text:
                continue
            span = session.scalar(select(SourceSpan).where(
                SourceSpan.source_block_id == block.id,
                SourceSpan.label == "raw_block",
            ))
            if span is None:
                session.add(SourceSpan(
                    source_page_id=page.id,
                    source_block_id=block.id,
                    label="raw_block",
                    raw_text=raw_block.text,
                    normalized_text=normalize_text(raw_block.text),
                    confidence=0.0,
                    review_status="pending",
                ))
            elif span.review_status not in {"approved", "reviewed"}:
                span.raw_text = raw_block.text
                span.normalized_text = normalize_text(raw_block.text)

        for table in raw_page.tables:
            for row_index, row in enumerate(table.rows):
                raw_row = " | ".join(cell or "" for cell in row).strip()
                if not raw_row:
                    continue
                label = f"raw_table:{table.index}:{row_index}"
                span = session.scalar(select(SourceSpan).where(
                    SourceSpan.source_page_id == page.id,
                    SourceSpan.label == label,
                ))
                if span is None:
                    session.add(SourceSpan(
                        source_page_id=page.id,
                        label=label,
                        raw_text=raw_row,
                        normalized_text=normalize_text(raw_row),
                        confidence=0.0,
                        review_status="pending",
                    ))
                elif span.review_status not in {"approved", "reviewed"}:
                    span.raw_text = raw_row
                    span.normalized_text = normalize_text(raw_row)

    existing_lessons = {
        (lesson.ordinal, lesson.start_pdf_page)
        for lesson in session.scalars(select(Lesson).where(Lesson.textbook_id == textbook_id)).all()
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


def run_job(session: Session, job: ImportJob) -> ImportJob:
    if job.state != ImportState.queued:
        return job
    job_id = job.id
    claimed = session.execute(
        update(ImportJob)
        .where(ImportJob.id == job_id, ImportJob.state == ImportState.queued)
        .values(
            state=ImportState.extracting,
            attempts=ImportJob.attempts + 1,
            stage="rights_check",
            failure_stage=None,
            message="Checking document processing rights.",
        )
    )
    if claimed.rowcount != 1:
        session.rollback()
        return session.get(ImportJob, job_id)
    session.commit()
    job = session.get(ImportJob, job_id)
    document = session.get(SourceDocument, job.source_document_id)
    if document is None:
        return _fail(
            session, job_id, "rights_check", "Source document no longer exists.",
            RuntimeError("source document missing"),
        )
    if document.rights_status != "authorized":
        return _fail(
            session, job_id, "rights_check",
            "Document rights must be marked authorized before extraction.",
            PermissionError("source rights are not authorized"),
        )
    document_id = document.id
    textbook_id = document.textbook_id
    source_document = document
    source_path = Path(document.source_path)
    checksum = document.sha256
    job.stage = "raw_extraction"
    job.failure_stage = None
    job.message = "Extracting raw PDF pages."
    session.commit()

    stage = "raw_extraction"
    try:
        if sha256_file(source_path) != checksum:
            raise PdfValidationError("Source checksum does not match registration")
        pages = extract_pages(source_path)
        raw = _raw_document(source_document, pages)

        stage = "raw_persistence"
        _set_stage(session, job_id, stage, "Persisting raw pages, blocks, and table rows.")
        with session.begin():
            _persist_raw_pages(session, document_id, textbook_id, pages)

        stage = "structured_extraction"
        _set_stage(session, job_id, stage, "Extracting structured knowledge from persisted source pages.")
        bundle = extract_knowledge(raw)

        stage = "validation"
        _set_stage(session, job_id, stage, "Validating source references and structured relationships.")
        invalid_pages = [
            warning for warning in bundle.warnings
            if warning.startswith("Missing source page ")
        ]
        if invalid_pages:
            raise ValueError("Structured records reference pages missing from the extraction")

        stage = "structured_persistence"
        _set_stage(session, job_id, stage, "Persisting structured records and provenance.")
        with session.begin():
            counts = persist_bundle(
                session,
                textbook_id,
                bundle,
                source_document_id=document_id,
            )

        stage = "quality_report"
        _set_stage(session, job_id, stage, "Building coverage and review quality report.")
        summary = report_dict(
            bundle,
            processed_pages=len(pages),
            total_pages=source_document.page_count or len(pages),
        )
        summary["persistence"] = counts
        job = session.get(ImportJob, job_id)
        if job is None:
            raise RuntimeError("Import job disappeared while writing quality report")
        job.state = ImportState.needs_review
        job.stage = "complete"
        job.failure_stage = None
        job.record_counts = counts
        job.quality_summary = summary
        job.message = "Raw and structured extraction completed; human review is required."
        session.commit()
    except PdfValidationError as error:
        return _fail(session, job_id, stage, "Source PDF validation failed.", error)
    except PermissionError as error:
        return _fail(session, job_id, stage, "Source rights check failed.", error)
    except (RuntimeError, OSError, ValueError, KeyError, TypeError, SQLAlchemyError) as error:
        return _fail(session, job_id, stage, "Extraction stage failed; retry is available if attempts remain.", error)
    session.refresh(job)
    return job


def recover_stale_jobs(
    session: Session,
    now: datetime | None = None,
    stale_after: timedelta = STALE_JOB_TIMEOUT,
) -> int:
    cutoff = (now or datetime.utcnow()) - stale_after
    stale_jobs = session.scalars(select(ImportJob).where(
        ImportJob.state == ImportState.extracting,
        ImportJob.updated_at < cutoff,
    )).all()
    for job in stale_jobs:
        expired_stage = job.stage
        if job.attempts < job.max_attempts:
            job.state = ImportState.queued
            job.stage = "queued"
            job.failure_stage = expired_stage
            job.message = "Recovered a stale worker job; queued for retry."
        else:
            job.state = ImportState.failed
            job.failure_stage = job.stage
            job.stage = "failed"
            job.message = "Worker job timed out after reaching the retry limit."
    if stale_jobs:
        session.commit()
    return len(stale_jobs)


def run_next_job(session: Session) -> ImportJob | None:
    recover_stale_jobs(session)
    job = session.scalar(
        select(ImportJob)
        .where(ImportJob.state == ImportState.queued)
        .order_by(ImportJob.created_at)
    )
    return run_job(session, job) if job else None
