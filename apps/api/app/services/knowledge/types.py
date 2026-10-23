from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any


@dataclass(frozen=True)
class SourceRef:
    pdf_page_number: int
    printed_page_number: str | None
    block_index: int | None = None
    table_index: int | None = None
    table_row_index: int | None = None


@dataclass(frozen=True)
class ExtractedRecord:
    source: SourceRef
    extraction_method: str = "deterministic-rule-v1"
    extraction_version: str = "structured-v1"
    review_status: str = "pending"
    validation_status: str = "unverified"


@dataclass(frozen=True)
class SectionRecord(ExtractedRecord):
    section_type: str = "unknown"
    title: str = ""


@dataclass(frozen=True)
class LessonRecord(ExtractedRecord):
    ordinal: int = 0
    title_ko: str = ""
    start_pdf_page: int = 0
    end_pdf_page: int | None = None
    topic: str | None = None


@dataclass(frozen=True)
class VocabularyRecord(ExtractedRecord):
    headword: str = ""
    normalized_headword: str = ""
    meanings_vi: list[str] = field(default_factory=list)
    part_of_speech: str | None = None
    topic: str | None = None


@dataclass(frozen=True)
class GrammarRecord(ExtractedRecord):
    pattern: str = ""
    normalized_pattern: str = ""
    explanation_vi: str | None = None
    usage_rules: str | None = None
    conjugation: str | None = None
    notes: str | None = None
    example_ids: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class SentenceRecord(ExtractedRecord):
    local_id: str = ""
    text_ko: str = ""
    text_vi: str | None = None
    grammar_patterns: list[str] = field(default_factory=list)
    vocabulary: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class DialogueTurnRecord(ExtractedRecord):
    local_id: str = ""
    group_id: str = ""
    turn_index: int = 0
    speaker: str | None = None
    text_ko: str = ""
    text_vi: str | None = None


@dataclass(frozen=True)
class PassageRecord(ExtractedRecord):
    local_id: str = ""
    title: str | None = None
    paragraphs: list[str] = field(default_factory=list)
    related_exercise_ids: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class ExerciseOptionRecord(ExtractedRecord):
    option_index: int = 0
    text: str = ""


@dataclass(frozen=True)
class ExerciseRecord(ExtractedRecord):
    local_id: str = ""
    group_id: str = ""
    parent_id: str | None = None
    exercise_type: str = "unknown"
    instruction: str | None = None
    prompt: str = ""
    options: list[ExerciseOptionRecord] = field(default_factory=list)
    answer: str | None = None
    answer_source: SourceRef | None = None
    passage_id: str | None = None
    listening_track_id: str | None = None


@dataclass(frozen=True)
class ListeningTrackRecord(ExtractedRecord):
    local_id: str = ""
    track_identifier: str = ""
    audio_status: str = "missing"


@dataclass(frozen=True)
class TranscriptRecord(ExtractedRecord):
    track_identifier: str = ""
    text: str = ""


@dataclass
class ExtractionBundle:
    schema_version: int = 1
    extraction_version: str = "structured-v1"
    lessons: list[LessonRecord] = field(default_factory=list)
    sections: list[SectionRecord] = field(default_factory=list)
    vocabulary: list[VocabularyRecord] = field(default_factory=list)
    grammar: list[GrammarRecord] = field(default_factory=list)
    sentences: list[SentenceRecord] = field(default_factory=list)
    dialogue_turns: list[DialogueTurnRecord] = field(default_factory=list)
    passages: list[PassageRecord] = field(default_factory=list)
    exercises: list[ExerciseRecord] = field(default_factory=list)
    listening_tracks: list[ListeningTrackRecord] = field(default_factory=list)
    transcripts: list[TranscriptRecord] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)
