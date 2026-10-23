from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import delete, select, update
from sqlalchemy.orm import Session

from app.config import get_settings
from app.database import get_session
from app.models import (
    AnswerKey,
    ContentProvenance,
    ContentReview,
    Dialogue,
    DialogueTurn,
    Exercise,
    ExerciseOption,
    GrammarPattern,
    ImportJob,
    ImportState,
    Lesson,
    ListeningTrack,
    LessonSection,
    Passage,
    Sentence,
    SourceBlock,
    SourceDocument,
    SourcePage,
    SourceSpan,
    Textbook,
    Transcript,
    Vocabulary,
    WordSense,
    sentence_grammar_patterns,
    sentence_vocabulary,
)
from app.schemas import DeleteDocumentResponse, ImportJobResponse, ImportRequest, ImportResponse
from app.security import get_current_owner
from app.services.pdf_engine import PdfValidationError, inspect_pdf
from app.services.pdf_importer import ImportPathError, resolve_pdf_path, sha256_file
from app.services.extraction_worker import queue_job
from app.services.private_storage import (
    PrivateStorageError,
    stage_private_file_deletion,
    store_private_pdf,
)
from app.services.quality import build_quality_report

router = APIRouter(prefix="/imports", tags=["imports"])


@router.post("", response_model=ImportResponse, status_code=status.HTTP_202_ACCEPTED)
def create_import(
    payload: ImportRequest,
    session: Session = Depends(get_session),
    owner_id: str = Depends(get_current_owner),
) -> ImportResponse:
    try:
        path = resolve_pdf_path(payload.source_path, get_settings().allowed_import_root)
    except ImportPathError as error:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(error)) from error

    try:
        actual_page_count = inspect_pdf(path)
    except (PdfValidationError, RuntimeError) as error:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(error)) from error
    digest = sha256_file(path)
    existing = session.scalar(
        select(SourceDocument).where(
            SourceDocument.owner_id == owner_id,
            SourceDocument.sha256 == digest,
        )
    )
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

    textbook = session.scalar(select(Textbook).where(
        Textbook.owner_id == owner_id,
        Textbook.volume_number == payload.volume_number,
    ))
    if textbook is None:
        textbook = Textbook(
            owner_id=owner_id,
            title=payload.title,
            level=payload.level,
            volume_number=payload.volume_number,
        )
        session.add(textbook)
        session.flush()

    try:
        private_path = store_private_pdf(
            path,
            get_settings().resolved_private_storage_root,
            owner_id,
            digest,
        )
    except PrivateStorageError as error:
        session.rollback()
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Unable to store private source") from error
    document = SourceDocument(
        owner_id=owner_id,
        textbook_id=textbook.id,
        filename=path.name,
        sha256=digest,
        page_count=actual_page_count,
        source_path=str(private_path),
        rights_status=payload.rights_status,
        rights_note=payload.rights_note,
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
def queue_import(
    job_id: int,
    session: Session = Depends(get_session),
    owner_id: str = Depends(get_current_owner),
) -> ImportJobResponse:
    job = session.scalar(select(ImportJob).join(SourceDocument).where(
        ImportJob.id == job_id,
        SourceDocument.owner_id == owner_id,
    ))
    if job is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Import job not found")
    if job.source_document.rights_status != "authorized":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Mark document rights as authorized before queuing extraction",
        )
    job = queue_job(session, job)
    return ImportJobResponse(id=job.id, source_document_id=job.source_document_id, state=job.state, message=job.message, created_at=job.created_at)


@router.get("/{job_id}", response_model=ImportJobResponse)
def get_import(
    job_id: int,
    session: Session = Depends(get_session),
    owner_id: str = Depends(get_current_owner),
) -> ImportJobResponse:
    job = session.scalar(select(ImportJob).join(SourceDocument).where(
        ImportJob.id == job_id,
        SourceDocument.owner_id == owner_id,
    ))
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
def import_report(
    job_id: int,
    session: Session = Depends(get_session),
    owner_id: str = Depends(get_current_owner),
) -> dict:
    job = session.scalar(select(ImportJob).join(SourceDocument).where(
        ImportJob.id == job_id,
        SourceDocument.owner_id == owner_id,
    ))
    if job is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Import job not found")
    return build_quality_report(session, job.source_document_id).__dict__


@router.delete("/documents/{document_id}", response_model=DeleteDocumentResponse)
def delete_document(
    document_id: int,
    session: Session = Depends(get_session),
    owner_id: str = Depends(get_current_owner),
) -> DeleteDocumentResponse:
    document = session.scalar(select(SourceDocument).where(
        SourceDocument.id == document_id,
        SourceDocument.owner_id == owner_id,
    ))
    if document is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Source document not found")

    source_path = Path(document.source_path)
    settings = get_settings()
    textbook_id = document.textbook_id
    other_document = session.scalar(select(SourceDocument.id).where(
        SourceDocument.textbook_id == textbook_id,
        SourceDocument.id != document_id,
    ))
    if other_document is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Delete or detach the other source documents for this textbook before purging its shared knowledge",
        )
    try:
        staged_path = stage_private_file_deletion(
            source_path,
            settings.resolved_private_storage_root,
            owner_id,
        )
    except (OSError, PrivateStorageError) as error:
        session.rollback()
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Unable to stage private source deletion") from error

    def purge_entities(model, entity_type: str, ids: list[int]) -> None:
        if not ids:
            return
        session.execute(delete(ContentProvenance).where(
            ContentProvenance.entity_type == entity_type,
            ContentProvenance.entity_id.in_(ids),
        ))
        session.execute(delete(ContentReview).where(
            ContentReview.entity_type == entity_type,
            ContentReview.entity_id.in_(ids),
        ))
        session.execute(delete(model).where(model.id.in_(ids)))

    try:
        session.execute(delete(ImportJob).where(ImportJob.source_document_id == document.id))
        page_ids = list(session.scalars(select(SourcePage.id).where(
            SourcePage.source_document_id == document.id,
        )))
        span_ids = list(session.scalars(select(SourceSpan.id).where(SourceSpan.source_page_id.in_(page_ids))))
        lesson_ids = list(session.scalars(select(Lesson.id).where(Lesson.textbook_id == textbook_id)))
        vocabulary_ids = list(session.scalars(select(Vocabulary.id).where(Vocabulary.lesson_id.in_(lesson_ids))))
        grammar_ids = list(session.scalars(select(GrammarPattern.id).where(GrammarPattern.lesson_id.in_(lesson_ids))))
        sentence_ids = list(session.scalars(select(Sentence.id).where(Sentence.lesson_id.in_(lesson_ids))))
        passage_ids = list(session.scalars(select(Passage.id).where(Passage.lesson_id.in_(lesson_ids))))
        dialogue_ids = list(session.scalars(select(Dialogue.id).where(Dialogue.lesson_id.in_(lesson_ids))))
        exercise_ids = list(session.scalars(select(Exercise.id).where(Exercise.lesson_id.in_(lesson_ids))))
        track_ids = list(session.scalars(select(ListeningTrack.id).where(ListeningTrack.lesson_id.in_(lesson_ids))))
        answer_ids = list(session.scalars(select(AnswerKey.id).where(AnswerKey.exercise_id.in_(exercise_ids))))
        transcript_ids = list(session.scalars(select(Transcript.id).where(Transcript.listening_track_id.in_(track_ids))))
        option_ids = list(session.scalars(select(ExerciseOption.id).where(ExerciseOption.exercise_id.in_(exercise_ids))))
        turn_ids = list(session.scalars(select(DialogueTurn.id).where(DialogueTurn.dialogue_id.in_(dialogue_ids))))
        sense_ids = list(session.scalars(select(WordSense.id).where(WordSense.vocabulary_id.in_(vocabulary_ids))))
        section_ids = list(session.scalars(select(LessonSection.id).where(LessonSection.lesson_id.in_(lesson_ids))))
        purge_entities(AnswerKey, "answer_key", answer_ids)
        purge_entities(Transcript, "transcript", transcript_ids)
        purge_entities(ExerciseOption, "exercise_option", option_ids)
        purge_entities(DialogueTurn, "dialogue_turn", turn_ids)
        if exercise_ids:
            session.execute(update(Exercise).where(
                Exercise.id.in_(exercise_ids),
            ).values(parent_exercise_id=None))
        purge_entities(Exercise, "exercise", exercise_ids)
        purge_entities(Dialogue, "dialogue", dialogue_ids)
        purge_entities(ListeningTrack, "listening_track", track_ids)
        purge_entities(Passage, "passage", passage_ids)
        if sentence_ids or vocabulary_ids:
            session.execute(delete(sentence_vocabulary).where(
                sentence_vocabulary.c.sentence_id.in_(sentence_ids or [-1])
                | sentence_vocabulary.c.vocabulary_id.in_(vocabulary_ids or [-1])
            ))
        if sentence_ids or grammar_ids:
            session.execute(delete(sentence_grammar_patterns).where(
                sentence_grammar_patterns.c.sentence_id.in_(sentence_ids or [-1])
                | sentence_grammar_patterns.c.grammar_pattern_id.in_(grammar_ids or [-1])
            ))
        purge_entities(Sentence, "sentence", sentence_ids)
        purge_entities(GrammarPattern, "grammar", grammar_ids)
        purge_entities(WordSense, "word_sense", sense_ids)
        purge_entities(LessonSection, "lesson_section", section_ids)
        purge_entities(Vocabulary, "vocabulary", vocabulary_ids)
        purge_entities(Lesson, "lesson", lesson_ids)
        session.execute(delete(ContentProvenance).where(ContentProvenance.source_span_id.in_(span_ids)))
        session.execute(delete(AnswerKey).where(AnswerKey.source_span_id.in_(span_ids)))
        session.execute(delete(Transcript).where(Transcript.source_span_id.in_(span_ids)))
        session.execute(delete(ExerciseOption).where(ExerciseOption.source_span_id.in_(span_ids)))
        session.execute(delete(DialogueTurn).where(DialogueTurn.source_span_id.in_(span_ids)))
        session.execute(delete(Vocabulary).where(Vocabulary.source_span_id.in_(span_ids)))
        session.execute(delete(GrammarPattern).where(GrammarPattern.source_span_id.in_(span_ids)))
        session.execute(delete(Passage).where(Passage.source_span_id.in_(span_ids)))
        session.execute(delete(SourceSpan).where(SourceSpan.id.in_(span_ids)))
        session.execute(delete(SourceBlock).where(SourceBlock.source_page_id.in_(page_ids)))
        session.execute(delete(SourcePage).where(SourcePage.id.in_(page_ids)))
        session.delete(document)
        session.execute(delete(Textbook).where(Textbook.id == textbook_id, Textbook.owner_id == owner_id))
        session.commit()
    except Exception as error:
        session.rollback()
        if staged_path.exists():
            staged_path.replace(source_path)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Unable to purge private document data") from error
    try:
        staged_path.unlink(missing_ok=True)
    except OSError as error:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Document data was deleted, but staged private-file cleanup failed",
        ) from error
    return DeleteDocumentResponse(deleted=True)
