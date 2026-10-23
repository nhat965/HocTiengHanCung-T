from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import get_settings
from app.database import get_session
from app.models import ImportJob, ImportState, SourceDocument, Textbook
from app.schemas import ImportJobResponse, ImportRequest, ImportResponse
from app.services.pdf_engine import PdfValidationError, inspect_pdf
from app.services.pdf_importer import ImportPathError, resolve_pdf_path, sha256_file
from app.services.extraction_worker import queue_job
from app.services.quality import build_quality_report

router = APIRouter(prefix="/imports", tags=["imports"])


@router.post("", response_model=ImportResponse, status_code=status.HTTP_202_ACCEPTED)
def create_import(payload: ImportRequest, session: Session = Depends(get_session)) -> ImportResponse:
    try:
        path = resolve_pdf_path(payload.source_path, get_settings().allowed_import_root)
    except ImportPathError as error:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(error)) from error

    try:
        actual_page_count = inspect_pdf(path)
    except (PdfValidationError, RuntimeError) as error:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(error)) from error
    digest = sha256_file(path)
    existing = session.scalar(select(SourceDocument).where(SourceDocument.sha256 == digest))
    if existing:
        latest_job = session.scalar(
            select(ImportJob).where(ImportJob.source_document_id == existing.id).order_by(ImportJob.id.desc())
        )
        if latest_job is None:
            latest_job = ImportJob(source_document_id=existing.id, state=ImportState.registered, message="Registered; not queued for extraction.")
            session.add(latest_job)
            session.commit()
            session.refresh(latest_job)
        return ImportResponse(
            job_id=latest_job.id,
            source_document_id=existing.id,
            state=latest_job.state,
            already_imported=True,
        )

    textbook = session.scalar(select(Textbook).where(Textbook.volume_number == payload.volume_number))
    if textbook is None:
        textbook = Textbook(title=payload.title, level=payload.level, volume_number=payload.volume_number)
        session.add(textbook)
        session.flush()

    document = SourceDocument(
        textbook_id=textbook.id,
        filename=path.name,
        sha256=digest,
        page_count=actual_page_count,
        source_path=str(path),
    )
    session.add(document)
    session.flush()
    job = ImportJob(
        source_document_id=document.id,
        state=ImportState.registered,
        message="Document registered. Queue extraction explicitly to begin processing.",
    )
    session.add(job)
    session.commit()
    session.refresh(job)
    return ImportResponse(job_id=job.id, source_document_id=document.id, state=job.state, already_imported=False)


@router.post("/{job_id}/queue", response_model=ImportJobResponse)
def queue_import(job_id: int, session: Session = Depends(get_session)) -> ImportJobResponse:
    job = session.get(ImportJob, job_id)
    if job is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Import job not found")
    job = queue_job(session, job)
    return ImportJobResponse(id=job.id, source_document_id=job.source_document_id, state=job.state, message=job.message, created_at=job.created_at)


@router.get("/{job_id}", response_model=ImportJobResponse)
def get_import(job_id: int, session: Session = Depends(get_session)) -> ImportJobResponse:
    job = session.get(ImportJob, job_id)
    if job is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Import job not found")
    return ImportJobResponse(
        id=job.id,
        source_document_id=job.source_document_id,
        state=job.state,
        message=job.message,
        created_at=job.created_at,
    )


@router.get("/{job_id}/report")
def import_report(job_id: int, session: Session = Depends(get_session)) -> dict:
    job = session.get(ImportJob, job_id)
    if job is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Import job not found")
    return build_quality_report(session, job.source_document_id).__dict__
