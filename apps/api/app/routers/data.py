from __future__ import annotations

import csv
import io
import json

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from sqlalchemy import String, cast, func, literal, select, union_all
from sqlalchemy.orm import Session

from app.database import get_session
from app.models import (
    AnswerKey, ContentProvenance, ContentReview, Dialogue, DialogueTurn,
    Exercise, ExerciseOption, GrammarPattern, Lesson, ListeningTrack, Passage,
    Sentence, SourceDocument, SourcePage, SourceSpan, Textbook, Transcript,
    Vocabulary, WordSense,
)
from app.schemas import ReviewCorrection, ReviewRecordResponse, ReviewUpdate
from app.security import get_current_owner
from app.services.data_export import SUPPORTED_DATASETS, export_dataset

router = APIRouter(tags=["data"])

_DIRECT_MODELS = {
    "lesson": Lesson,
    "vocabulary": Vocabulary,
    "grammar": GrammarPattern,
    "sentence": Sentence,
    "passage": Passage,
    "exercise": Exercise,
    "listening_track": ListeningTrack,
    "dialogue_turn": DialogueTurn,
    "word_sense": WordSense,
    "exercise_option": ExerciseOption,
    "answer_key": AnswerKey,
    "transcript": Transcript,
}


def _owned_entity(session: Session, entity_type: str, entity_id: int, owner_id: str):
    model = _DIRECT_MODELS.get(entity_type)
    if model is None:
        return None
    if model is Lesson:
        query = select(model).join(Textbook).where(model.id == entity_id, Textbook.owner_id == owner_id)
    elif model is DialogueTurn:
        query = (select(model).join(Dialogue, model.dialogue_id == Dialogue.id)
                 .join(Lesson, Dialogue.lesson_id == Lesson.id).join(Textbook)
                 .where(model.id == entity_id, Textbook.owner_id == owner_id))
    elif model is WordSense:
        query = (select(model).join(Vocabulary).join(Lesson).join(Textbook)
                 .where(model.id == entity_id, Textbook.owner_id == owner_id))
    elif model in {ExerciseOption, AnswerKey}:
        query = (select(model).join(Exercise).join(Lesson).join(Textbook)
                 .where(model.id == entity_id, Textbook.owner_id == owner_id))
    elif model is Transcript:
        query = (select(model).join(ListeningTrack).join(Lesson).join(Textbook)
                 .where(model.id == entity_id, Textbook.owner_id == owner_id))
    else:
        query = select(model).join(Lesson, model.lesson_id == Lesson.id).join(Textbook).where(
            model.id == entity_id, Textbook.owner_id == owner_id,
        )
    return session.scalar(query)


def _preview(row) -> str:
    for field in ("headword", "meaning_vi", "answer_text", "pattern", "text_ko", "text", "prompt", "title", "track_identifier"):
        value = getattr(row, field, None)
        if value:
            return str(value)[:160]
    return f"{type(row).__name__} #{row.id}"


def _source_projection(source_span_column, owner_id: str):
    """Return scalar provenance fields that can be UNIONed into the queue."""
    if source_span_column is None:
        return literal(None).label("source_page_number"), literal(None).label("source_printed_page_number"), literal(None).label("source_text")
    return (
        select(SourcePage.pdf_page_number)
        .join(SourceSpan, SourceSpan.source_page_id == SourcePage.id)
        .join(SourceDocument, SourcePage.source_document_id == SourceDocument.id)
        .where(SourceSpan.id == source_span_column, SourceDocument.owner_id == owner_id)
        .scalar_subquery()
        .label("source_page_number"),
        select(SourcePage.printed_page_number)
        .join(SourceSpan, SourceSpan.source_page_id == SourcePage.id)
        .join(SourceDocument, SourcePage.source_document_id == SourceDocument.id)
        .where(SourceSpan.id == source_span_column, SourceDocument.owner_id == owner_id)
        .scalar_subquery()
        .label("source_printed_page_number"),
        select(SourceSpan.normalized_text)
        .join(SourcePage, SourceSpan.source_page_id == SourcePage.id)
        .join(SourceDocument, SourcePage.source_document_id == SourceDocument.id)
        .where(SourceSpan.id == source_span_column, SourceDocument.owner_id == owner_id)
        .scalar_subquery()
        .label("source_text"),
    )


def _review_response(
    session: Session,
    row,
    entity_type: str,
    source_span_id: int | None,
    owner_id: str,
) -> ReviewRecordResponse:
    source_page_number = None
    source_printed_page_number = None
    source_text = None
    if source_span_id is not None:
        source = session.execute(
            select(SourcePage.pdf_page_number, SourcePage.printed_page_number, SourceSpan.normalized_text)
            .join(SourceSpan, SourceSpan.source_page_id == SourcePage.id)
            .join(SourceDocument, SourcePage.source_document_id == SourceDocument.id)
            .where(SourceSpan.id == source_span_id, SourceDocument.owner_id == owner_id)
        ).first()
        if source:
            source_page_number, source_printed_page_number, source_text = source
    return ReviewRecordResponse(
        entity_type=entity_type, entity_id=row.id,
        review_status=row.review_status, preview=_preview(row), version=row.version,
        source_span_id=source_span_id, source_page_number=source_page_number,
        source_printed_page_number=source_printed_page_number, source_text=source_text,
    )


def _entity_lesson_id(session: Session, row) -> int | None:
    if isinstance(row, Lesson):
        return row.id
    if hasattr(row, "lesson_id"):
        return row.lesson_id
    if isinstance(row, WordSense):
        return session.scalar(select(Vocabulary.lesson_id).where(Vocabulary.id == row.vocabulary_id))
    if isinstance(row, (ExerciseOption, AnswerKey)):
        exercise_id = row.exercise_id
        return session.scalar(select(Exercise.lesson_id).where(Exercise.id == exercise_id))
    if isinstance(row, Transcript):
        return session.scalar(select(ListeningTrack.lesson_id).where(ListeningTrack.id == row.listening_track_id))
    if isinstance(row, DialogueTurn):
        return session.scalar(select(Dialogue.lesson_id).where(Dialogue.id == row.dialogue_id))
    return None


def _validate_provenance(
    session: Session,
    row,
    entity_type: str,
    entity_id: int,
    source_span_id: int,
    owner_id: str,
) -> None:
    source = session.execute(
        select(
            SourceSpan.id,
            SourceSpan.normalized_text,
            SourcePage.pdf_page_number,
            SourceDocument.owner_id,
            SourceDocument.textbook_id,
        )
        .join(SourcePage, SourceSpan.source_page_id == SourcePage.id)
        .join(SourceDocument, SourcePage.source_document_id == SourceDocument.id)
        .where(SourceSpan.id == source_span_id)
    ).first()
    if source is None or source.owner_id != owner_id or not source.normalized_text.strip():
        raise HTTPException(status_code=422, detail="Approval requires a non-empty owner-scoped source span")

    lesson_id = _entity_lesson_id(session, row)
    lesson = session.get(Lesson, lesson_id) if lesson_id is not None else None
    if lesson is None or lesson.textbook_id != source.textbook_id:
        raise HTTPException(status_code=422, detail="Source reference does not belong to the record lesson")
    if (
        lesson.start_pdf_page is not None
        and source.pdf_page_number < lesson.start_pdf_page
    ) or (
        lesson.end_pdf_page is not None
        and source.pdf_page_number > lesson.end_pdf_page
    ):
        raise HTTPException(status_code=422, detail="Source page does not belong to the record lesson")

    provenance = session.scalar(select(ContentProvenance.id).where(
        ContentProvenance.entity_type == entity_type,
        ContentProvenance.entity_id == entity_id,
        ContentProvenance.source_span_id == source_span_id,
    ))
    if provenance is None:
        raise HTTPException(status_code=422, detail="Approval requires matching content provenance")
    direct_span = getattr(row, "source_span_id", None)
    if direct_span is not None and direct_span != source_span_id:
        raise HTTPException(status_code=422, detail="Source reference does not match the record")


@router.get("/review", response_model=list[ReviewRecordResponse])
def review_queue(
    session: Session = Depends(get_session),
    owner_id: str = Depends(get_current_owner),
    review_status: str = Query("pending", max_length=32),
    offset: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
) -> list[ReviewRecordResponse]:
    queries = []
    for entity_type, model in _DIRECT_MODELS.items():
        preview_column = next(
            (getattr(model, field) for field in (
                "headword", "meaning_vi", "answer_text", "pattern", "text_ko", "text", "prompt", "title", "track_identifier",
            ) if hasattr(model, field)),
            literal(""),
        )
        source_span_column = (
            model.source_span_id if hasattr(model, "source_span_id") else literal(None)
        )
        source_page_number, source_printed_page_number, source_text = _source_projection(
            model.source_span_id if hasattr(model, "source_span_id") else None, owner_id,
        )
        projection = select(
            literal(entity_type).label("entity_type"),
            model.id.label("entity_id"),
            model.review_status.label("review_status"),
            cast(func.coalesce(preview_column, ""), String).label("preview"),
            model.version.label("version"),
            source_span_column.label("source_span_id"),
            source_page_number,
            source_printed_page_number,
            source_text,
        )
        if model is DialogueTurn:
            projection = projection.join(Dialogue).join(Lesson).join(Textbook).where(
                Textbook.owner_id == owner_id, model.review_status == review_status,
            )
        elif model is WordSense:
            projection = projection.join(Vocabulary).join(Lesson).join(Textbook).where(
                Textbook.owner_id == owner_id, model.review_status == review_status,
            )
        elif model in {ExerciseOption, AnswerKey}:
            projection = projection.join(Exercise).join(Lesson).join(Textbook).where(
                Textbook.owner_id == owner_id, model.review_status == review_status,
            )
        elif model is Transcript:
            projection = projection.join(ListeningTrack).join(Lesson).join(Textbook).where(
                Textbook.owner_id == owner_id, model.review_status == review_status,
            )
        elif model is Lesson:
            projection = projection.join(Textbook).where(
                Textbook.owner_id == owner_id, model.review_status == review_status,
            )
        else:
            projection = projection.join(Lesson).join(Textbook).where(
                Textbook.owner_id == owner_id, model.review_status == review_status,
            )
        queries.append(projection)
    queue = union_all(*queries).subquery()
    rows = session.execute(
        select(queue).order_by(queue.c.entity_type, queue.c.entity_id).offset(offset).limit(limit)
    ).mappings().all()
    return [ReviewRecordResponse(**dict(row)) for row in rows]


@router.post("/review/{entity_type}/{entity_id}", response_model=ReviewRecordResponse)
def update_review(
    entity_type: str,
    entity_id: int,
    payload: ReviewUpdate,
    session: Session = Depends(get_session),
    owner_id: str = Depends(get_current_owner),
) -> ReviewRecordResponse:
    row = _owned_entity(session, entity_type, entity_id, owner_id)
    if row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Review record not found")
    current_version = int(getattr(row, "version", 1))
    source_span_id = payload.source_span_id or getattr(row, "source_span_id", None)
    if row.review_status == "approved" and payload.status != "approved":
        raise HTTPException(status_code=409, detail="Approved records cannot be moved without a correction workflow")
    if payload.expected_version is None or payload.expected_version != current_version:
        raise HTTPException(status_code=409, detail="Record version changed; reload before review")
    if payload.status == "approved":
        if source_span_id is None:
            raise HTTPException(status_code=422, detail="Approval requires a source reference")
        if payload.reviewer_action not in {"compared_to_source", "corrected"}:
            raise HTTPException(status_code=422, detail="Approval requires an explicit source comparison action")
        required_checks = {"source_text", "source_page", "source_position", "semantic_alignment", "structure"}
        if not required_checks.issubset(set(payload.checks)):
            raise HTTPException(status_code=422, detail="Approval requires all source, page, semantic, and structure checks")
        _validate_provenance(session, row, entity_type, entity_id, source_span_id, owner_id)
    row.review_status = payload.status
    row.version = current_version + 1
    session.add(ContentReview(
        entity_type=entity_type, entity_id=entity_id, status=payload.status,
        note=payload.note, reviewer_id=owner_id,
        source_span_id=source_span_id, entity_version=current_version,
        reviewer_action=payload.reviewer_action, checks=payload.checks, change_set=None,
    ))
    session.commit()
    return _review_response(session, row, entity_type, source_span_id, owner_id)


_CORRECTION_FIELDS = {
    "vocabulary": {"headword"},
    "word_sense": {"meaning_vi"},
    "grammar": {"pattern", "explanation_vi"},
    "sentence": {"text_ko", "text_vi"},
    "exercise": {"prompt"},
}


@router.post("/review/{entity_type}/{entity_id}/correction", response_model=ReviewRecordResponse)
def correct_review_candidate(
    entity_type: str,
    entity_id: int,
    payload: ReviewCorrection,
    session: Session = Depends(get_session),
    owner_id: str = Depends(get_current_owner),
) -> ReviewRecordResponse:
    row = _owned_entity(session, entity_type, entity_id, owner_id)
    if row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Review record not found")
    if payload.field not in _CORRECTION_FIELDS.get(entity_type, set()):
        raise HTTPException(status_code=422, detail="Correction field is not supported for this entity")
    if row.review_status in {"approved", "reviewed"}:
        raise HTTPException(status_code=409, detail="Approved records cannot be corrected in review queue")
    current_version = int(getattr(row, "version", 1))
    if payload.expected_version != current_version:
        raise HTTPException(status_code=409, detail="Record version changed; reload before correction")
    before = getattr(row, payload.field)
    if before == payload.value:
        return _review_response(session, row, entity_type, getattr(row, "source_span_id", None), owner_id)
    setattr(row, payload.field, payload.value)
    if hasattr(row, "content_origin"):
        row.content_origin = "human_corrected"
    row.version = current_version + 1
    session.add(ContentReview(
        entity_type=entity_type,
        entity_id=entity_id,
        status=row.review_status,
        note=payload.note or f"Human correction: {payload.field}",
        reviewer_id=owner_id,
        source_span_id=getattr(row, "source_span_id", None),
        entity_version=current_version,
        reviewer_action="corrected",
        checks=[],
        change_set={"field": payload.field, "before": before, "after": payload.value},
    ))
    session.commit()
    return _review_response(session, row, entity_type, getattr(row, "source_span_id", None), owner_id)


@router.get("/textbooks/{textbook_id}/exports/{dataset}")
def dataset_export(
    textbook_id: int,
    dataset: str,
    session: Session = Depends(get_session),
    owner_id: str = Depends(get_current_owner),
    review_status: str = Query("approved", max_length=32),
    format: str = Query("json", pattern="^(json|jsonl|csv)$"),
) -> Response:
    textbook = session.scalar(select(Textbook).where(
        Textbook.id == textbook_id, Textbook.owner_id == owner_id,
    ))
    if textbook is None:
        raise HTTPException(status_code=404, detail="Textbook not found")
    if dataset not in SUPPORTED_DATASETS:
        raise HTTPException(status_code=404, detail="Dataset not found")
    if format == "csv" and dataset != "vocabulary":
        raise HTTPException(status_code=422, detail="CSV is supported for vocabulary only")
    exported = export_dataset(session, textbook, dataset, review_status)
    if format == "jsonl":
        lines = [json.dumps({"metadata": exported["metadata"]}, ensure_ascii=False)]
        lines.extend(json.dumps(record, ensure_ascii=False) for record in exported["records"])
        return Response("\n".join(lines) + "\n", media_type="application/x-ndjson")
    if format == "csv":
        stream = io.StringIO()
        metadata = exported["metadata"]
        fields = [
            "schema_version", "source_identifier", "extraction_version", "export_timestamp",
            "id", "lesson_id", "headword", "normalized_headword", "meanings_vi",
            "review_status", "source_span_id", "content_origin",
        ]
        writer = csv.DictWriter(stream, fieldnames=fields)
        writer.writeheader()
        for record in exported["records"]:
            writer.writerow({
                "schema_version": metadata["schema_version"],
                "source_identifier": metadata["source_identifier"],
                "extraction_version": metadata["extraction_version"],
                "export_timestamp": metadata["export_timestamp"],
                **record,
                "meanings_vi": " | ".join(record["meanings_vi"]),
            })
        return Response(stream.getvalue(), media_type="text/csv; charset=utf-8")
    return Response(json.dumps(exported, ensure_ascii=False), media_type="application/json")
