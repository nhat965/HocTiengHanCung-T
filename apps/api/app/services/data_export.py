"""Owner-scoped, metadata-rich knowledge dataset exports."""
from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import (
    AnswerKey, Dialogue, DialogueTurn, Exercise, ExerciseOption, GrammarPattern,
    Lesson, ListeningTrack, Passage, Sentence, SourceDocument, Textbook,
    Transcript, Vocabulary, WordSense,
)

SCHEMA_VERSION = "1.0"
SUPPORTED_DATASETS = {
    "vocabulary", "grammar", "sentences", "dialogues", "reading",
    "exercises", "listening",
}


def _meta(textbook: Textbook, dataset: str, review_status: str) -> dict:
    return {
        "schema_version": SCHEMA_VERSION,
        "dataset": dataset,
        "source_identifier": f"textbook:{textbook.id}",
        "extraction_version": "structured-v1",
        "review_status": review_status,
        "export_timestamp": datetime.now(timezone.utc).isoformat(),
    }


def export_dataset(
    session: Session,
    textbook: Textbook,
    dataset: str,
    review_status: str,
) -> dict:
    if dataset not in SUPPORTED_DATASETS:
        raise ValueError(f"Unsupported dataset: {dataset}")
    lesson_ids = select(Lesson.id).where(Lesson.textbook_id == textbook.id)
    records: list[dict] = []
    if dataset == "vocabulary":
        for row in session.scalars(select(Vocabulary).where(
            Vocabulary.lesson_id.in_(lesson_ids), Vocabulary.review_status == review_status,
        ).order_by(Vocabulary.id)).all():
            records.append({
                "id": row.id, "lesson_id": row.lesson_id, "headword": row.headword,
                "normalized_headword": row.normalized_headword,
                "meanings_vi": list(session.scalars(select(WordSense.meaning_vi).where(
                    WordSense.vocabulary_id == row.id,
                )).all()),
                "review_status": row.review_status, "source_span_id": row.source_span_id,
            })
    elif dataset == "grammar":
        rows = session.scalars(select(GrammarPattern).where(
            GrammarPattern.lesson_id.in_(lesson_ids), GrammarPattern.review_status == review_status,
        ).order_by(GrammarPattern.id)).all()
        records = [{
            "id": row.id, "lesson_id": row.lesson_id, "pattern": row.pattern,
            "normalized_pattern": row.normalized_pattern, "explanation_vi": row.explanation_vi,
            "usage_rules": row.usage_rules, "conjugation": row.conjugation,
            "notes": row.notes, "review_status": row.review_status,
            "source_span_id": row.source_span_id,
        } for row in rows]
    elif dataset == "sentences":
        rows = session.scalars(select(Sentence).where(
            Sentence.lesson_id.in_(lesson_ids), Sentence.review_status == review_status,
        ).order_by(Sentence.id)).all()
        records = [{
            "id": row.id, "identity_id": row.identity_id, "lesson_id": row.lesson_id, "text_ko": row.text_ko,
            "text_vi": row.text_vi, "review_status": row.review_status,
            "source_span_id": row.source_span_id,
            "vocabulary_ids": [item.id for item in row.vocabulary_items],
            "grammar_pattern_ids": [item.id for item in row.grammar_patterns],
        } for row in rows]
    elif dataset == "dialogues":
        rows = session.scalars(select(Dialogue).where(Dialogue.lesson_id.in_(lesson_ids)).order_by(Dialogue.id)).all()
        records = [{
            "id": row.id, "lesson_id": row.lesson_id, "group_identifier": row.group_identifier,
            "topic": row.topic, "source_span_id": row.source_span_id,
            "turns": [{
                "turn_index": turn.turn_index, "speaker": turn.speaker,
                "text_ko": turn.text, "text_vi": turn.text_vi,
                "review_status": turn.review_status, "source_span_id": turn.source_span_id,
            } for turn in session.scalars(select(DialogueTurn).where(
                DialogueTurn.dialogue_id == row.id, DialogueTurn.review_status == review_status,
            ).order_by(DialogueTurn.turn_index)).all()],
        } for row in rows]
        records = [row for row in records if row["turns"]]
    elif dataset == "reading":
        rows = session.scalars(select(Passage).where(
            Passage.lesson_id.in_(lesson_ids), Passage.review_status == review_status,
        ).order_by(Passage.id)).all()
        records = [{"id": row.id, "lesson_id": row.lesson_id, "title": row.title,
                    "text": row.text, "review_status": row.review_status,
                    "source_span_id": row.source_span_id} for row in rows]
    elif dataset == "exercises":
        rows = session.scalars(select(Exercise).where(
            Exercise.lesson_id.in_(lesson_ids), Exercise.review_status == review_status,
        ).order_by(Exercise.id)).all()
        records = [{
            "id": row.id, "lesson_id": row.lesson_id, "type": row.exercise_type,
            "group_identifier": row.group_identifier, "parent_exercise_id": row.parent_exercise_id,
            "prompt": row.prompt, "options": list(session.scalars(select(ExerciseOption.text).where(
                ExerciseOption.exercise_id == row.id,
            ).order_by(ExerciseOption.option_index)).all()),
            "answers": list(session.scalars(select(AnswerKey.answer_text).where(
                AnswerKey.exercise_id == row.id,
            )).all()), "review_status": row.review_status, "source_span_id": row.source_span_id,
        } for row in rows]
    else:
        rows = session.scalars(select(ListeningTrack).where(
            ListeningTrack.lesson_id.in_(lesson_ids), ListeningTrack.review_status == review_status,
        ).order_by(ListeningTrack.id)).all()
        records = [{
            "id": row.id, "lesson_id": row.lesson_id,
            "track_identifier": row.track_identifier, "audio_status": row.audio_status,
            "asset_reference": row.asset_reference, "review_status": row.review_status,
            "source_span_id": row.source_span_id,
            "transcripts": list(session.scalars(select(Transcript.text).where(
                Transcript.listening_track_id == row.id,
            )).all()),
        } for row in rows]
    metadata = _meta(textbook, dataset, review_status)
    metadata["record_count"] = len(records)
    return {"metadata": metadata, "records": records}
