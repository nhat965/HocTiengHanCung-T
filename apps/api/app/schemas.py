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


class DeleteDocumentResponse(BaseModel):
    deleted: bool
