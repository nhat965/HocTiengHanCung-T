from collections import Counter
from dataclasses import asdict, dataclass

from app.services.knowledge.types import ExtractionBundle


@dataclass(frozen=True)
class KnowledgeQualityReport:
    extraction_coverage: dict[str, int]
    structural_counts: dict[str, int]
    validation: dict[str, int | str]
    human_review: dict[str, int]
    warnings: list[str]


def build_quality_report(bundle: ExtractionBundle, processed_pages: int, total_pages: int) -> KnowledgeQualityReport:
    transcript_ids = {
        "".join(character for character in record.track_identifier.upper() if character.isalnum())
        for record in bundle.transcripts
    }
    matched_tracks = sum(
        "".join(character for character in track.track_identifier.upper() if character.isalnum()) in transcript_ids
        for track in bundle.listening_tracks
    )
    duplicate_words = sum(count - 1 for count in Counter(
        item.normalized_headword for item in bundle.vocabulary
    ).values() if count > 1)
    reviewed = sum(
        record.review_status in {"approved", "reviewed"}
        for records in (
            bundle.lessons, bundle.sections, bundle.vocabulary, bundle.grammar,
            bundle.sentences, bundle.dialogue_turns, bundle.passages,
            bundle.exercises, bundle.listening_tracks, bundle.transcripts,
        )
        for record in records
    )
    total_records = sum((
        len(bundle.lessons), len(bundle.sections), len(bundle.vocabulary),
        len(bundle.grammar), len(bundle.sentences), len(bundle.dialogue_turns),
        len(bundle.passages), len(bundle.exercises), len(bundle.listening_tracks),
        len(bundle.transcripts),
    ))
    return KnowledgeQualityReport(
        extraction_coverage={
            "total_pages": total_pages,
            "processed_pages": processed_pages,
            "unprocessed_pages": max(0, total_pages - processed_pages),
        },
        structural_counts={
            "lessons": len(bundle.lessons),
            "sections": len(bundle.sections),
            "vocabulary": len(bundle.vocabulary),
            "vocabulary_without_meanings": sum(not item.meanings_vi for item in bundle.vocabulary),
            "duplicate_vocabulary_candidates": duplicate_words,
            "grammar_patterns": len(bundle.grammar),
            "grammar_without_explanation": sum(not item.explanation_vi for item in bundle.grammar),
            "grammar_without_examples": sum(not item.example_ids for item in bundle.grammar),
            "sentences": len(bundle.sentences),
            "dialogue_turns": len(bundle.dialogue_turns),
            "reading_passages": len(bundle.passages),
            "exercises": len(bundle.exercises),
            "exercises_without_answer": sum(item.answer is None for item in bundle.exercises if item.parent_id),
            "listening_tracks": len(bundle.listening_tracks),
            "transcripts": len(bundle.transcripts),
            "tracks_with_transcript": matched_tracks,
        },
        validation={
            "records_with_page_reference": sum(record.source.pdf_page_number > 0 for records in (
                bundle.lessons, bundle.sections, bundle.vocabulary, bundle.grammar,
                bundle.sentences, bundle.dialogue_turns, bundle.passages,
                bundle.exercises, bundle.listening_tracks, bundle.transcripts,
            ) for record in records),
            "records_total": total_records,
            "status": "review_required" if bundle.warnings else "unverified",
        },
        human_review={
            "reviewed": reviewed,
            "pending": max(0, total_records - reviewed),
        },
        warnings=list(bundle.warnings),
    )


def report_dict(bundle: ExtractionBundle, processed_pages: int, total_pages: int) -> dict:
    return asdict(build_quality_report(bundle, processed_pages, total_pages))
