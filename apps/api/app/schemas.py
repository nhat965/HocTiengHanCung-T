from datetime import datetime

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
