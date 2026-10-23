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


class ImportResponse(BaseModel):
    job_id: int
    source_document_id: int
    state: ImportState
    already_imported: bool


class ImportJobResponse(BaseModel):
    id: int
    source_document_id: int
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


class LessonResponse(BaseModel):
    id: int
    ordinal: int | None
    title: str
    start_pdf_page: int | None
    end_pdf_page: int | None
    review_status: str


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


class ExerciseResponse(BaseModel):
    id: int
    prompt: str
    exercise_type: str
    options: list[str] = Field(default_factory=list)
    answer: str | None = None
    source_page_number: int | None = None
    review_status: str


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


class ReviewRecordResponse(BaseModel):
    entity_type: str
    entity_id: int
    review_status: str
    source_page_number: int | None = None
    preview: str


class DeleteDocumentResponse(BaseModel):
    deleted: bool
