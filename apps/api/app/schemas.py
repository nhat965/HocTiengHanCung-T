from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

from app.models import ImportState


class HealthResponse(BaseModel):
    status: str
    database: str


class ImportRequest(BaseModel):
    source_path: str = Field(min_length=1)
    title: str = Field(min_length=1, max_length=255)
    level: str = Field(min_length=1, max_length=64)
    volume_number: int = Field(ge=1, le=6)
    rights_status: Literal["unverified", "authorized", "restricted"] = "unverified"
    rights_note: str | None = Field(default=None, max_length=2000)
    page_start: int | None = Field(default=None, ge=1)
    page_end: int | None = Field(default=None, ge=1)


class ImportResponse(BaseModel):
    job_id: int
    source_document_id: int
    state: ImportState
    already_imported: bool


class ImportJobResponse(BaseModel):
    id: int
    source_document_id: int
    page_start: int | None = None
    page_end: int | None = None
    state: ImportState
    stage: str
    failure_stage: str | None = None
    attempts: int
    max_attempts: int
    record_counts: dict[str, int] | None = None
    message: str | None
    created_at: datetime


class TextbookResponse(BaseModel):
    id: int
    title: str
    level: str
    volume_number: int
    lesson_count: int = 0
    completed_lessons: int = 0
    progress_percent: int = 0
    data_status: str = "empty"


class LessonResponse(BaseModel):
    id: int
    ordinal: int | None
    title: str
    start_pdf_page: int | None
    end_pdf_page: int | None
    review_status: str
    vocabulary_count: int = 0
    grammar_count: int = 0
    progress_status: str = "not_started"
    last_opened_at: datetime | None = None


class VocabularyResponse(BaseModel):
    id: int
    headword: str
    meanings_vi: list[str] = Field(default_factory=list)
    source_page_number: int | None = None
    review_status: str


class GrammarResponse(BaseModel):
    id: int
    pattern: str
    explanation_vi: str | None = None
    source_page_number: int | None = None
    review_status: str


class ExerciseOptionResponse(BaseModel):
    option_index: int
    text: str


class ExerciseResponse(BaseModel):
    id: int
    prompt: str
    exercise_type: str
    options: list[ExerciseOptionResponse] = Field(default_factory=list)
    source_page_number: int | None = None
    review_status: str
    parent_exercise_id: int | None = None
    has_children: bool = False


class SentenceResponse(BaseModel):
    id: int
    identity_id: int | None = None
    text_ko: str
    text_vi: str | None
    source_page_number: int | None
    review_status: str


class PassageResponse(BaseModel):
    id: int
    title: str | None
    text: str
    source_page_number: int | None
    review_status: str


class ListeningResponse(BaseModel):
    id: int
    track_identifier: str
    audio_status: str
    transcript_available: bool
    source_page_number: int | None
    review_status: str


class DialogueTurnResponse(BaseModel):
    turn_index: int
    speaker: str | None
    text_ko: str
    text_vi: str | None


class DialogueResponse(BaseModel):
    id: int
    group_identifier: str | None
    topic: str | None
    turns: list[DialogueTurnResponse] = Field(default_factory=list)
    source_page_number: int | None


class ReviewUpdate(BaseModel):
    status: Literal["pending_review", "approved", "rejected", "unresolved"]
    note: str | None = Field(default=None, max_length=2000)
    expected_version: int | None = Field(default=None, ge=1)
    source_span_id: int | None = Field(default=None, ge=1)
    reviewer_action: Literal["compared_to_source", "corrected", "flagged"] | None = None
    checks: list[Literal["source_text", "source_page", "source_position", "semantic_alignment", "structure"]] = Field(default_factory=list)


class ReviewCorrection(BaseModel):
    expected_version: int = Field(ge=1)
    field: Literal["headword", "meaning_vi", "pattern", "explanation_vi", "text_ko", "text_vi", "prompt"]
    value: str = Field(min_length=1, max_length=4000)
    note: str | None = Field(default=None, max_length=2000)


class ReviewRecordResponse(BaseModel):
    entity_type: str
    entity_id: int
    review_status: str
    source_page_number: int | None = None
    source_printed_page_number: str | None = None
    source_text: str | None = None
    preview: str
    version: int
    source_span_id: int | None = None


class VocabularyReviewRequest(BaseModel):
    answer_vi: str = Field(min_length=1, max_length=500)


class VocabularyReviewResponse(BaseModel):
    vocabulary_id: int
    correct: bool
    status: str
    repetitions: int
    interval_days: int
    next_review_at: datetime


class StudyProgressResponse(BaseModel):
    approved_vocabulary: int
    learned_vocabulary: int
    due_vocabulary: int
    attempts: int
    completed_lessons: int = 0
    total_lessons: int = 0
    last_lesson_id: int | None = None
    last_lesson_title: str | None = None


class StudyFlashcardResponse(BaseModel):
    vocabulary_id: int
    headword: str
    meanings_vi: list[str] = Field(default_factory=list)
    examples: list[str] = Field(default_factory=list)
    status: str
    next_review_at: datetime | None = None


class LessonProgressResponse(BaseModel):
    lesson_id: int
    status: str
    completed_at: datetime | None = None
    last_opened_at: datetime | None = None


class ExerciseAttemptRequest(BaseModel):
    answer: str = Field(min_length=1, max_length=1000)


class ExerciseAttemptResponse(BaseModel):
    attempt_id: int
    exercise_id: int
    correct: bool | None
    answer_revealed: str | None = None


class GrammarNoteRequest(BaseModel):
    note: str = Field(max_length=4000)


class GrammarNoteResponse(BaseModel):
    grammar_id: int
    note: str
    updated_at: datetime | None = None


class DeleteDocumentResponse(BaseModel):
    deleted: bool
