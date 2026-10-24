from __future__ import annotations

from dataclasses import asdict, dataclass
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import (
    AnswerKey, ContentProvenance, Exercise, GrammarPattern, Lesson,
    LessonSection, ListeningTrack, Sentence, SourceDocument, SourcePage,
    SourceSpan, Transcript, Vocabulary, WordSense,
)


@dataclass(frozen=True)
class QualityReport:
    source_document_id: int
    source_coverage: dict[str, int]
    structural_coverage: dict[str, int]
    vocabulary: dict[str, int]
    grammar: dict[str, int]
    exercises: dict[str, int]
    listening: dict[str, int]
    provenance: dict[str, int]
    quality_status: dict[str, int]
    lesson_breakdown: dict[str, dict[str, int]]
    coverage_note: str
    accuracy_note: str


def build_quality_report(session: Session, source_document_id: int) -> QualityReport:
    document = session.get(SourceDocument, source_document_id)
    if document is None:
        raise ValueError("Source document not found")
    pages = session.scalars(select(SourcePage).where(SourcePage.source_document_id == source_document_id)).all()
    lessons = session.scalars(select(Lesson).where(Lesson.textbook_id == document.textbook_id)).all()
    lesson_ids = [lesson.id for lesson in lessons]
    vocabulary = session.scalars(select(Vocabulary).where(Vocabulary.lesson_id.in_(lesson_ids))).all() if lesson_ids else []
    grammar = session.scalars(select(GrammarPattern).where(GrammarPattern.lesson_id.in_(lesson_ids))).all() if lesson_ids else []
    exercises = session.scalars(select(Exercise).where(Exercise.lesson_id.in_(lesson_ids))).all() if lesson_ids else []
    tracks = session.scalars(select(ListeningTrack).where(ListeningTrack.lesson_id.in_(lesson_ids))).all() if lesson_ids else []
    track_ids = [track.id for track in tracks]
    transcripts = session.scalars(select(Transcript).where(Transcript.listening_track_id.in_(track_ids))).all() if track_ids else []
    exercise_ids = [item.id for item in exercises]
    answers = session.scalars(select(AnswerKey).where(AnswerKey.exercise_id.in_(exercise_ids))).all() if exercise_ids else []
    answer_exercise_ids = {item.exercise_id for item in answers}
    vocabulary_ids = [item.id for item in vocabulary]
    sense_word_ids = set(session.scalars(select(WordSense.vocabulary_id).where(
        WordSense.vocabulary_id.in_(vocabulary_ids),
    )).all()) if vocabulary_ids else set()
    transcript_track_ids = {item.listening_track_id for item in transcripts}
    sections = session.scalars(select(LessonSection).where(LessonSection.lesson_id.in_(lesson_ids))).all() if lesson_ids else []
    structured = [*lessons, *vocabulary, *grammar, *exercises, *tracks]
    statuses: dict[str, int] = {}
    for record in structured:
        value = getattr(record, "review_status", "extracted")
        statuses[value] = statuses.get(value, 0) + 1
    provenance_rows = session.scalars(
        select(ContentProvenance).join(SourceSpan).join(SourcePage).where(
            SourcePage.source_document_id == source_document_id,
        )
    ).all()
    known = {(row.entity_type, row.entity_id) for row in provenance_rows}
    expected = {
        (kind, row.id)
        for kind, rows in (
            ("lesson", lessons), ("vocabulary", vocabulary), ("grammar", grammar),
            ("exercise", exercises), ("listening_track", tracks),
        )
        for row in rows
    }
    sentence_with_grammar = session.scalars(select(Sentence).where(
        Sentence.lesson_id.in_(lesson_ids), Sentence.grammar_patterns.any(),
    )).all() if lesson_ids else []
    return QualityReport(
        source_document_id=source_document_id,
        source_coverage={
            "total_pages": document.page_count or len(pages), "processed_pages": len(pages),
            "failed_pages": max(0, (document.page_count or len(pages)) - len(pages)),
            "ocr_required_pages": sum(page.needs_ocr for page in pages),
            "unreadable_regions": sum(page.needs_ocr for page in pages),
        },
        structural_coverage={
            "lessons_found": len(lessons), "sections_found": len(sections),
            "missing_sections": sum(not any(item.lesson_id == lesson.id for item in sections) for lesson in lessons),
            "duplicate_sections": len(sections) - len({(item.lesson_id, item.section_type, item.source_page_number) for item in sections}),
        },
        vocabulary={
            "total_records": len(vocabulary), "records_with_meanings": len(sense_word_ids),
            "records_without_meanings": len(vocabulary) - len(sense_word_ids),
            "duplicate_entries": len(vocabulary) - len({(item.lesson_id, item.normalized_headword) for item in vocabulary}),
            "alignment_issues": sum(item.source_span_id is None for item in vocabulary),
        },
        grammar={
            "total_patterns": len(grammar),
            "patterns_with_explanations": sum(bool(item.explanation_vi) for item in grammar),
            "patterns_with_examples": len(sentence_with_grammar),
            "missing_fields": sum(not item.explanation_vi for item in grammar),
        },
        exercises={
            "total_questions": len(exercises),
            "questions_with_answers": sum(item.id in answer_exercise_ids for item in exercises),
            "questions_without_answers": sum(item.id not in answer_exercise_ids for item in exercises),
            "orphan_questions": sum(item.parent_exercise_id is not None and item.parent_exercise_id not in set(exercise_ids) for item in exercises),
        },
        listening={
            "total_tracks": len(tracks), "tracks_with_transcripts": len(transcript_track_ids),
            "unmatched_transcripts": sum(item.listening_track_id not in set(track_ids) for item in transcripts),
            "missing_audio": sum(item.audio_status != "available" or not item.asset_reference for item in tracks),
        },
        provenance={
            "records_with_exact_source_references": len(known & expected),
            "records_with_unresolved_references": len(expected - known),
            "records_requiring_review": sum(getattr(item, "review_status", "pending") not in {"approved", "reviewed"} for item in structured),
        },
        quality_status=statuses,
        lesson_breakdown={
            str(lesson.id): {
                "sections": sum(item.lesson_id == lesson.id for item in sections),
                "vocabulary": sum(item.lesson_id == lesson.id for item in vocabulary),
                "grammar": sum(item.lesson_id == lesson.id for item in grammar),
                "exercises": sum(item.lesson_id == lesson.id for item in exercises),
                "listening_tracks": sum(item.lesson_id == lesson.id for item in tracks),
            }
            for lesson in lessons
        },
        coverage_note="Counts describe persisted extraction output; they do not prove semantic correctness.",
        accuracy_note="Accuracy is intentionally not estimated without licensed human-reviewed ground truth.",
    )


def write_quality_report(report: QualityReport, output_dir: Path) -> tuple[Path, Path]:
    import json
    output_dir.mkdir(parents=True, exist_ok=True)
    json_path = output_dir / f"source-{report.source_document_id}-quality.json"
    markdown_path = output_dir / f"source-{report.source_document_id}-quality.md"
    json_path.write_text(json.dumps(asdict(report), ensure_ascii=False, indent=2), encoding="utf-8")
    markdown_path.write_text("# PDF extraction quality report\n\n" + "\n".join(f"- **{key}**: {value}" for key, value in asdict(report).items()) + "\n", encoding="utf-8")
    return json_path, markdown_path
