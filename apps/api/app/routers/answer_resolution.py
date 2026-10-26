from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database import get_session
from app.models import (
    AnswerKey, AnswerResolutionCandidate, ContentProvenance, ContentReview,
    Exercise, ExerciseAnswerContext, Lesson, SourceDocument, SourcePage, SourceSpan, Textbook,
)
from app.schemas import (
    AnswerResolutionApproveRequest, AnswerResolutionResponse, AnswerResolutionReviewRequest,
)
from app.security import get_current_owner

router = APIRouter(tags=["answer-resolution"])
_REQUIRED_CHECKS = {"source_text", "source_page", "source_position", "semantic_alignment", "structure"}


def _owned_candidate(session: Session, candidate_id: int, owner_id: str) -> AnswerResolutionCandidate:
    candidate = session.scalar(select(AnswerResolutionCandidate).join(SourceDocument).where(
        AnswerResolutionCandidate.id == candidate_id, SourceDocument.owner_id == owner_id,
    ))
    if candidate is None:
        raise HTTPException(status_code=404, detail="Answer resolution candidate not found")
    return candidate


def _span_page(session: Session, span_id: int | None, source_document_id: int) -> int | None:
    if span_id is None:
        return None
    return session.scalar(select(SourcePage.pdf_page_number).join(SourceSpan).where(
        SourceSpan.id == span_id, SourcePage.source_document_id == source_document_id,
    ))


def _context(session: Session, candidate: AnswerResolutionCandidate) -> ExerciseAnswerContext | None:
    return session.get(ExerciseAnswerContext, candidate.question_context_id) if candidate.question_context_id else None


def _response(session: Session, candidate: AnswerResolutionCandidate) -> AnswerResolutionResponse:
    context = _context(session, candidate)
    exercise = session.get(Exercise, context.exercise_id) if context else None
    return AnswerResolutionResponse(
        id=candidate.id, status=candidate.status, compound_key=candidate.compound_key,
        lesson_number=candidate.lesson_number, skill_section=candidate.skill_section,
        exercise_group=candidate.exercise_group, question_number=candidate.question_number,
        question_context_id=context.id if context else None,
        exercise_id=exercise.id if exercise else None,
        question_prompt=exercise.prompt if exercise else None,
        question_page_number=_span_page(session, context.question_source_span_id, candidate.source_document_id) if context else None,
        question_source_span_id=context.question_source_span_id if context else None,
        answer_text=candidate.answer_text,
        answer_page_number=_span_page(session, candidate.answer_source_span_id, candidate.source_document_id),
        answer_source_span_id=candidate.answer_source_span_id,
        match_reason=candidate.match_reason, reviewer_note=candidate.reviewer_note,
        version=candidate.version,
    )


def _validate_context(session: Session, candidate: AnswerResolutionCandidate, context: ExerciseAnswerContext) -> None:
    if context.source_document_id != candidate.source_document_id:
        raise HTTPException(status_code=422, detail="Question context uses another source document")
    exercise = session.scalar(select(Exercise).join(Lesson).join(
        SourceDocument, SourceDocument.textbook_id == Lesson.textbook_id,
    ).where(
        Exercise.id == context.exercise_id,
        SourceDocument.id == candidate.source_document_id,
        Lesson.textbook_id == SourceDocument.textbook_id,
    ))
    if exercise is None:
        raise HTTPException(status_code=422, detail="Question does not belong to candidate source textbook")
    if _span_page(session, context.question_source_span_id, candidate.source_document_id) is None:
        raise HTTPException(status_code=422, detail="Question context has invalid source provenance")
    if candidate.answer_source_span_id is None or _span_page(session, candidate.answer_source_span_id, candidate.source_document_id) is None:
        raise HTTPException(status_code=422, detail="Answer candidate has invalid source provenance")


def _history(session: Session, candidate: AnswerResolutionCandidate, action: str, note: str | None, *, change_set: dict | None = None) -> None:
    session.add(ContentReview(
        entity_type="answer_resolution_candidate", entity_id=candidate.id,
        status=candidate.status, note=note, reviewer_id=candidate.owner_id,
        source_span_id=candidate.answer_source_span_id, entity_version=candidate.version - 1,
        reviewer_action=action, checks=[], change_set=change_set,
    ))


@router.get("/answer-resolution", response_model=list[AnswerResolutionResponse])
def answer_resolution_queue(
    session: Session = Depends(get_session),
    owner_id: str = Depends(get_current_owner),
    status_filter: str | None = Query(None, alias="status", max_length=200),
    limit: int = Query(50, ge=1, le=100),
) -> list[AnswerResolutionResponse]:
    query = select(AnswerResolutionCandidate).join(SourceDocument).where(SourceDocument.owner_id == owner_id)
    if status_filter:
        statuses = [item.strip() for item in status_filter.split(",") if item.strip()]
        query = query.where(AnswerResolutionCandidate.status.in_(statuses))
    rows = session.scalars(query.order_by(AnswerResolutionCandidate.id).limit(limit)).all()
    return [_response(session, row) for row in rows]


@router.post("/answer-resolution/{candidate_id}/review", response_model=AnswerResolutionResponse)
def review_answer_resolution(
    candidate_id: int,
    payload: AnswerResolutionReviewRequest,
    session: Session = Depends(get_session),
    owner_id: str = Depends(get_current_owner),
) -> AnswerResolutionResponse:
    candidate = _owned_candidate(session, candidate_id, owner_id)
    if candidate.status == "approved":
        raise HTTPException(status_code=409, detail="Approved answer resolution cannot be remapped")
    if candidate.version != payload.expected_version:
        raise HTTPException(status_code=409, detail="Candidate version changed; reload before review")
    before = candidate.question_context_id
    if payload.action == "reject":
        candidate.status = "unresolved"
        candidate.match_reason = "Reviewer rejected the proposed question-answer pair"
        candidate.reviewer_note = payload.note
    else:
        if payload.action == "select" and not payload.note:
            raise HTTPException(status_code=422, detail="Selecting a replacement context requires a reviewer note")
        context_id = payload.question_context_id or candidate.question_context_id
        context = session.get(ExerciseAnswerContext, context_id) if context_id else None
        if context is None:
            raise HTTPException(status_code=422, detail="Reviewer must select a source-backed question context")
        _validate_context(session, candidate, context)
        candidate.question_context_id = context.id
        candidate.status = "verified"
        candidate.match_reason = "Reviewer confirmed source-backed question-answer pair"
        candidate.reviewer_note = payload.note
    candidate.version += 1
    _history(session, candidate, "corrected" if payload.action == "select" else payload.action, payload.note,
             change_set={"question_context_id": {"before": before, "after": candidate.question_context_id}})
    session.commit()
    return _response(session, candidate)


@router.post("/answer-resolution/{candidate_id}/approve", response_model=AnswerResolutionResponse)
def approve_answer_resolution(
    candidate_id: int,
    payload: AnswerResolutionApproveRequest,
    session: Session = Depends(get_session),
    owner_id: str = Depends(get_current_owner),
) -> AnswerResolutionResponse:
    candidate = _owned_candidate(session, candidate_id, owner_id)
    if candidate.version != payload.expected_version:
        raise HTTPException(status_code=409, detail="Candidate version changed; reload before approval")
    if candidate.status != "verified":
        raise HTTPException(status_code=422, detail="Only reviewer-verified candidates can create an approved answer key")
    if not _REQUIRED_CHECKS.issubset(set(payload.checks)):
        raise HTTPException(status_code=422, detail="Approval requires all source and structural checks")
    context = _context(session, candidate)
    if context is None:
        raise HTTPException(status_code=422, detail="Candidate has no selected question context")
    _validate_context(session, candidate, context)
    existing = session.scalar(select(AnswerKey).where(
        AnswerKey.exercise_id == context.exercise_id,
        AnswerKey.answer_index == candidate.compound_key,
    ))
    if existing is not None and existing.review_status == "approved" and (
        existing.answer_text != candidate.answer_text or existing.source_span_id != candidate.answer_source_span_id
    ):
        raise HTTPException(status_code=409, detail="Approved answer key cannot be overwritten")
    if existing is not None and existing.content_origin == "human_corrected" and (
        existing.answer_text != candidate.answer_text or existing.source_span_id != candidate.answer_source_span_id
    ):
        raise HTTPException(status_code=409, detail="Human-corrected answer key cannot be overwritten")
    if existing is None:
        existing = AnswerKey(
            exercise_id=context.exercise_id, answer_text=candidate.answer_text,
            source_span_id=candidate.answer_source_span_id, answer_index=candidate.compound_key,
            review_status="approved",
        )
        session.add(existing)
        session.flush()
    elif existing.review_status != "approved":
        existing.answer_text = candidate.answer_text
        existing.source_span_id = candidate.answer_source_span_id
        existing.answer_index = candidate.compound_key
        existing.review_status = "approved"
        existing.version += 1
    provenance = session.scalar(select(ContentProvenance.id).where(
        ContentProvenance.entity_type == "answer_key", ContentProvenance.entity_id == existing.id,
        ContentProvenance.source_span_id == candidate.answer_source_span_id,
        ContentProvenance.extraction_method == "answer-resolution-v1",
    ))
    if provenance is None:
        session.add(ContentProvenance(
            entity_type="answer_key", entity_id=existing.id, source_span_id=candidate.answer_source_span_id,
            extraction_method="answer-resolution-v1", extraction_version="answer-resolution-v1",
        ))
    candidate.status = "approved"
    candidate.reviewer_note = payload.note
    candidate.version += 1
    session.add(ContentReview(
        entity_type="answer_key", entity_id=existing.id, status="approved", note=payload.note,
        reviewer_id=owner_id, source_span_id=candidate.answer_source_span_id,
        entity_version=existing.version, reviewer_action="compared_to_source", checks=payload.checks,
        change_set={"resolution_candidate_id": candidate.id},
    ))
    _history(session, candidate, "compared_to_source", payload.note)
    session.commit()
    return _response(session, candidate)
