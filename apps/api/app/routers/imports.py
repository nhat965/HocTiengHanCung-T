from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import get_settings
from app.database import get_session
from app.models import ImportJob, ImportState, SourceDocument, Textbook
from app.schemas import ImportJobResponse, ImportRequest, ImportResponse
from app.services.pdf_importer import ImportPathError, page_count, resolve_pdf_path, sha256_file

router = APIRouter(prefix="/imports", tags=["imports"])


@router.post("", response_model=ImportResponse, status_code=status.HTTP_202_ACCEPTED)
def create_import(payload: ImportRequest, session: Session = Depends(get_session)) -> ImportResponse:
    try:
        path = resolve_pdf_path(payload.source_path, get_settings().allowed_import_root)
    except ImportPathError as error:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(error)) from error

    digest = sha256_file(path)
    existing = session.scalar(select(SourceDocument).where(SourceDocument.sha256 == digest))
    if existing:
        latest_job = session.scalar(
            select(ImportJob).where(ImportJob.source_document_id == existing.id).order_by(ImportJob.id.desc())
        )
        if latest_job is None:
            latest_job = ImportJob(source_document_id=existing.id, state=ImportState.needs_review)
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
        page_count=page_count(path),
        source_path=str(path),
    )
    session.add(document)
    session.flush()
    job = ImportJob(
        source_document_id=document.id,
        state=ImportState.needs_review,
        message="Document registered. Extraction pipeline is not yet scheduled in Phase 1.",
    )
    session.add(job)
    session.commit()
    session.refresh(job)
    return ImportResponse(job_id=job.id, source_document_id=document.id, state=job.state, already_imported=False)


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
