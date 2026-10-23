from datetime import datetime
from enum import Enum

from sqlalchemy import DateTime, Enum as SqlEnum, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class ImportState(str, Enum):
    queued = "queued"
    extracting = "extracting"
    needs_review = "needs_review"
    completed = "completed"
    failed = "failed"


class Textbook(Base):
    __tablename__ = "textbooks"
    __table_args__ = (UniqueConstraint("volume_number", name="uq_textbooks_volume_number"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    title: Mapped[str] = mapped_column(String(255))
    level: Mapped[str] = mapped_column(String(64))
    volume_number: Mapped[int] = mapped_column(Integer)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    source_documents: Mapped[list["SourceDocument"]] = relationship(back_populates="textbook")


class SourceDocument(Base):
    __tablename__ = "source_documents"
    __table_args__ = (UniqueConstraint("sha256", name="uq_source_documents_sha256"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    textbook_id: Mapped[int] = mapped_column(ForeignKey("textbooks.id"), index=True)
    filename: Mapped[str] = mapped_column(String(512))
    sha256: Mapped[str] = mapped_column(String(64))
    page_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    source_path: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    textbook: Mapped[Textbook] = relationship(back_populates="source_documents")
    import_jobs: Mapped[list["ImportJob"]] = relationship(back_populates="source_document")


class ImportJob(Base):
    __tablename__ = "import_jobs"

    id: Mapped[int] = mapped_column(primary_key=True)
    source_document_id: Mapped[int] = mapped_column(ForeignKey("source_documents.id"), index=True)
    state: Mapped[ImportState] = mapped_column(SqlEnum(ImportState), default=ImportState.queued)
    message: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    source_document: Mapped[SourceDocument] = relationship(back_populates="import_jobs")
