"""Database-backed raw and structured PDF extraction worker."""
from __future__ import annotations

from datetime import datetime, timedelta
import logging
from pathlib import Path
from typing import Any
from uuid import uuid4

from sqlalchemy import and_, or_, select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.models import ImportJob, ImportState, SourceBlock, SourceDocument, SourcePage, SourceSpan
from app.services.knowledge.persistence import persist_bundle
from app.services.knowledge.pipeline import extract_knowledge
from app.services.knowledge.quality import report_dict
from app.services.pdf_engine import PdfValidationError, RawPage, extract_pages
from app.services.pdf_importer import sha256_file
from app.services.segmentation import normalize_text

logger = logging.getLogger(__name__)
STALE_JOB_TIMEOUT = timedelta(minutes=60)
WORKER_LEASE_DURATION = timedelta(minutes=60)


class WorkerLeaseLost(RuntimeError):
    """Raised when a worker tries to write after its import lease expired."""


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
        job.worker_token = None
        job.lease_expires_at = None
        session.commit()
        session.refresh(job)
    return job


def _owned_job(
    session: Session,
    job_id: int,
    worker_token: str,
    *,
    lock: bool = False,
) -> ImportJob:
    query = select(ImportJob).where(
        ImportJob.id == job_id,
        ImportJob.state == ImportState.extracting,
        ImportJob.worker_token == worker_token,
        ImportJob.lease_expires_at > datetime.utcnow(),
    )
    if lock:
        query = query.with_for_update()
    job = session.scalar(query)
    if job is None:
        raise WorkerLeaseLost(f"Worker lease lost for import job {job_id}")
    return job


def _set_stage(
    session: Session,
    job_id: int,
    stage: str,
    message: str,
    worker_token: str,
) -> ImportJob:
    job = _owned_job(session, job_id, worker_token, lock=True)
    job.state = ImportState.extracting
    job.stage = stage
    job.failure_stage = None
    job.message = message
    job.lease_expires_at = datetime.utcnow() + WORKER_LEASE_DURATION
    session.commit()
    return job


def _fail(
    session: Session,
    job_id: int,
    stage: str,
    message: str,
    error: Exception,
    worker_token: str,
) -> ImportJob | None:
    session.rollback()
    try:
        job = _owned_job(session, job_id, worker_token, lock=True)
    except WorkerLeaseLost:
        session.rollback()
        return session.get(ImportJob, job_id)
    sqlstate = getattr(getattr(error, "orig", None), "sqlstate", None)
    diagnostic = f"{type(error).__name__}, SQLSTATE {sqlstate}" if sqlstate else type(error).__name__
    job.state = ImportState.failed
    job.stage = "failed"
    job.failure_stage = stage
    job.message = f"{message} ({diagnostic})"
    job.worker_token = None
    job.lease_expires_at = None
    session.commit()
    session.refresh(job)
    logger.error("Import job %s failed at stage %s (%s)", job_id, stage, diagnostic)
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
                "sanitized_nul_count": page.sanitized_nul_count,
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



def _claim_job(session: Session, job_id: int | None = None) -> tuple[ImportJob | None, str | None]:
    query = select(ImportJob).where(ImportJob.state == ImportState.queued)
    if job_id is not None:
        query = query.where(ImportJob.id == job_id)
    else:
        query = query.order_by(ImportJob.created_at)
    candidate = session.scalar(query.with_for_update(skip_locked=True))
    if candidate is None:
        session.rollback()
        return (session.get(ImportJob, job_id) if job_id is not None else None), None
    worker_token = uuid4().hex
    candidate.state = ImportState.extracting
    candidate.attempts += 1
    candidate.stage = "rights_check"
    candidate.failure_stage = None
    candidate.message = "Checking document processing rights."
    candidate.worker_token = worker_token
    candidate.lease_expires_at = datetime.utcnow() + WORKER_LEASE_DURATION
    session.commit()
    session.refresh(candidate)
    return candidate, worker_token


def _lock_source_document(session: Session, document_id: int) -> SourceDocument:
    document = session.scalar(
        select(SourceDocument).where(SourceDocument.id == document_id).with_for_update()
    )
    if document is None:
        raise RuntimeError("Source document disappeared while persisting extraction")
    return document


def _process_claimed_job(session: Session, job: ImportJob, worker_token: str) -> ImportJob | None:
    job_id = job.id
    document = session.get(SourceDocument, job.source_document_id)
    if document is None:
        return _fail(
            session, job_id, "rights_check", "Source document no longer exists.",
            RuntimeError("source document missing"), worker_token,
        )
    if document.rights_status != "authorized":
        return _fail(
            session, job_id, "rights_check",
            "Document rights must be marked authorized before extraction.",
            PermissionError("source rights are not authorized"), worker_token,
        )
    document_id = document.id
    textbook_id = document.textbook_id
    source_document = document
    source_path = Path(document.source_path)
    checksum = document.sha256
    start = job.page_start or document.page_start or 1
    end = job.page_end or document.page_end or document.page_count or start
    page_range = None
    if (
        job.page_start is not None
        or job.page_end is not None
        or document.page_start is not None
        or document.page_end is not None
    ):
        page_range = range(start, end + 1)
    total_pages = document.page_count or end
    stage = "raw_extraction"
    try:
        _set_stage(session, job_id, "raw_extraction", "Extracting raw PDF pages.", worker_token)
        if sha256_file(source_path) != checksum:
            raise PdfValidationError("Source checksum does not match registration")
        # Range belongs to this import job. Fall back to the old document
        # fields only for jobs created before the range migration.
        pages = extract_pages(source_path, page_range)
        raw = _raw_document(source_document, pages)
        raw_inventory = {
            "scope": {
                "pdf_page_start": start,
                "pdf_page_end": end,
            },
            "printed_page_mapping": {
                str(page.pdf_page_number): page.printed_page_number for page in pages
            },
            "processed_pages": len(pages),
            "extractable_text_pages": sum(bool(page.text.strip()) for page in pages),
            "ocr_needed_pages": [page.pdf_page_number for page in pages if page.needs_ocr],
            "image_count": sum(page.image_count for page in pages),
            "table_count": sum(len(page.tables) for page in pages),
        }
        session.rollback()
        with session.begin():
            _owned_job(session, job_id, worker_token, lock=True)
            _lock_source_document(session, document_id).inventory_metadata = raw_inventory

        stage = "raw_persistence"
        _set_stage(session, job_id, stage, "Persisting raw pages, blocks, and table rows.", worker_token)
        with session.begin():
            _owned_job(session, job_id, worker_token, lock=True)
            _lock_source_document(session, document_id)
            _persist_raw_pages(session, document_id, textbook_id, pages)

        stage = "structured_extraction"
        _set_stage(session, job_id, stage, "Extracting structured knowledge from persisted source pages.", worker_token)
        bundle = extract_knowledge(raw)
        session.rollback()
        with session.begin():
            _owned_job(session, job_id, worker_token, lock=True)
            document = _lock_source_document(session, document_id)
            if document is None:
                raise RuntimeError("Source document disappeared while extracting structured knowledge")
            inventory = dict(document.inventory_metadata or {})
            inventory["lessons"] = [
                {
                    "ordinal": lesson.ordinal,
                    "title": lesson.title_ko,
                    "pdf_page_start": lesson.start_pdf_page,
                    "pdf_page_end": lesson.end_pdf_page,
                }
                for lesson in bundle.lessons
            ]
            inventory["section_types"] = sorted({section.section_type for section in bundle.sections})
            inventory["appendix_boundary"] = None
            document.inventory_metadata = inventory

        stage = "validation"
        _set_stage(session, job_id, stage, "Validating source references and structured relationships.", worker_token)
        invalid_pages = [
            warning for warning in bundle.warnings
            if warning.startswith("Missing source page ")
        ]
        if invalid_pages:
            raise ValueError("Structured records reference pages missing from the extraction")

        stage = "structured_persistence"
        _set_stage(session, job_id, stage, "Persisting structured records and provenance.", worker_token)
        session.rollback()
        with session.begin():
            _owned_job(session, job_id, worker_token, lock=True)
            _lock_source_document(session, document_id)
            counts = persist_bundle(
                session,
                textbook_id,
                bundle,
                source_document_id=document_id,
            )

        stage = "quality_report"
        _set_stage(session, job_id, stage, "Building coverage and review quality report.", worker_token)
        summary = report_dict(
            bundle,
            processed_pages=len(pages),
            total_pages=total_pages,
        )
        summary["persistence"] = counts
        summary["scope"] = {"pdf_page_start": start, "pdf_page_end": end}
        summary["text_sanitization"] = {
            "nul_replacements": sum(page.sanitized_nul_count for page in pages),
        }
        with session.begin():
            job = _owned_job(session, job_id, worker_token, lock=True)
            job.state = ImportState.needs_review
            job.stage = "complete"
            job.failure_stage = None
            job.record_counts = counts
            job.quality_summary = summary
            job.message = "Raw and structured extraction completed; human review is required."
            job.worker_token = None
            job.lease_expires_at = None
    except PdfValidationError as error:
        return _fail(session, job_id, stage, "Source PDF validation failed.", error, worker_token)
    except PermissionError as error:
        return _fail(session, job_id, stage, "Source rights check failed.", error, worker_token)
    except WorkerLeaseLost:
        session.rollback()
        return session.get(ImportJob, job_id)
    except (RuntimeError, OSError, ValueError, KeyError, TypeError, SQLAlchemyError) as error:
        return _fail(session, job_id, stage, "Extraction stage failed; retry is available if attempts remain.", error, worker_token)
    return session.get(ImportJob, job_id)


def recover_stale_jobs(
    session: Session,
    now: datetime | None = None,
    stale_after: timedelta = STALE_JOB_TIMEOUT,
) -> int:
    cutoff = (now or datetime.utcnow()) - stale_after
    current_time = now or datetime.utcnow()
    stale_jobs = session.scalars(
        select(ImportJob)
        .where(
            ImportJob.state == ImportState.extracting,
            or_(
                and_(ImportJob.lease_expires_at.is_not(None), ImportJob.lease_expires_at <= current_time),
                and_(ImportJob.lease_expires_at.is_(None), ImportJob.updated_at < cutoff),
            ),
        )
        .order_by(ImportJob.id)
        .with_for_update(skip_locked=True)
    ).all()
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
        job.worker_token = None
        job.lease_expires_at = None
    if stale_jobs:
        session.commit()
    return len(stale_jobs)


def run_next_job(session: Session) -> ImportJob | None:
    recover_stale_jobs(session)
    job, worker_token = _claim_job(session)
    if job is None or worker_token is None:
        return job
    return _process_claimed_job(session, job, worker_token)


def run_job(session: Session, job: ImportJob) -> ImportJob | None:
    if job is None or job.state != ImportState.queued:
        return job
    claimed, worker_token = _claim_job(session, job.id)
    if claimed is None or worker_token is None:
        return claimed
    return _process_claimed_job(session, claimed, worker_token)
