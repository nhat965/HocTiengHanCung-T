from __future__ import annotations

import csv
import io
import json

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database import get_session
from app.models import (
    ContentReview, Dialogue, DialogueTurn, Exercise, GrammarPattern, Lesson,
    ListeningTrack, Passage, Sentence, Textbook, Vocabulary,
)
from app.schemas import ReviewRecordResponse, ReviewUpdate
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
    else:
        query = select(model).join(Lesson, model.lesson_id == Lesson.id).join(Textbook).where(
            model.id == entity_id, Textbook.owner_id == owner_id,
        )
    return session.scalar(query)


def _preview(row) -> str:
    for field in ("headword", "pattern", "text_ko", "text", "prompt", "title", "track_identifier"):
        value = getattr(row, field, None)
        if value:
            return str(value)[:160]
    return f"{type(row).__name__} #{row.id}"


@router.get("/review", response_model=list[ReviewRecordResponse])
def review_queue(
    session: Session = Depends(get_session),
    owner_id: str = Depends(get_current_owner),
    review_status: str = Query("pending", max_length=32),
    offset: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
) -> list[ReviewRecordResponse]:
    records: list[ReviewRecordResponse] = []
    for entity_type, model in _DIRECT_MODELS.items():
        if model is DialogueTurn:
            rows = session.scalars(select(model).join(Dialogue).join(Lesson).join(Textbook).where(
                Textbook.owner_id == owner_id, model.review_status == review_status,
            )).all()
        elif model is Lesson:
            rows = session.scalars(select(model).join(Textbook).where(
                Textbook.owner_id == owner_id, model.review_status == review_status,
            )).all()
        else:
            rows = session.scalars(select(model).join(Lesson).join(Textbook).where(
                Textbook.owner_id == owner_id, model.review_status == review_status,
            )).all()
        records.extend(ReviewRecordResponse(
            entity_type=entity_type, entity_id=row.id,
            review_status=row.review_status, preview=_preview(row),
        ) for row in rows)
    records.sort(key=lambda item: (item.entity_type, item.entity_id))
    return records[offset:offset + limit]


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
    row.review_status = payload.status
    session.add(ContentReview(
        entity_type=entity_type, entity_id=entity_id, status=payload.status,
        note=payload.note, reviewer_id=owner_id,
    ))
    session.commit()
    return ReviewRecordResponse(
        entity_type=entity_type, entity_id=entity_id,
        review_status=row.review_status, preview=_preview(row),
    )


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
            "review_status", "source_span_id",
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
