from datetime import datetime
from enum import Enum

from sqlalchemy import BigInteger, DateTime, Enum as SqlEnum, ForeignKey, Integer, Table, UniqueConstraint, Column
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from app.text_sanitizer import SanitizedJSON as JSON
from app.text_sanitizer import SanitizedString as String
from app.text_sanitizer import SanitizedText as Text

sentence_vocabulary = Table(
    "sentence_vocabulary",
    Base.metadata,
    Column("sentence_id", ForeignKey("sentences.id"), primary_key=True),
    Column("vocabulary_id", ForeignKey("vocabulary.id"), primary_key=True),
)
sentence_grammar_patterns = Table(
    "sentence_grammar_patterns",
    Base.metadata,
    Column("sentence_id", ForeignKey("sentences.id"), primary_key=True),
    Column("grammar_pattern_id", ForeignKey("grammar_patterns.id"), primary_key=True),
)


class ImportState(str, Enum):
    registered = "registered"
    queued = "queued"
    extracting = "extracting"
    extracted = "extracted"
    needs_review = "needs_review"
    completed = "completed"
    failed = "failed"


class Textbook(Base):
    __tablename__ = "textbooks"
    __table_args__ = (UniqueConstraint("owner_id", "volume_number", name="uq_textbooks_owner_volume"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    owner_id: Mapped[str] = mapped_column(String(128), default="local-owner", index=True)
    title: Mapped[str] = mapped_column(String(255))
    level: Mapped[str] = mapped_column(String(64))
    volume_number: Mapped[int] = mapped_column(Integer)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    source_documents: Mapped[list["SourceDocument"]] = relationship(back_populates="textbook")


class SourceDocument(Base):
    __tablename__ = "source_documents"
    __table_args__ = (UniqueConstraint("owner_id", "sha256", name="uq_source_documents_owner_sha256"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    owner_id: Mapped[str] = mapped_column(String(128), default="local-owner", index=True)
    textbook_id: Mapped[int] = mapped_column(ForeignKey("textbooks.id"), index=True)
    filename: Mapped[str] = mapped_column(String(512))
    sha256: Mapped[str] = mapped_column(String(64))
    page_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    file_size: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    # Deprecated legacy range columns; new registrations keep these null and
    # store the requested range on ImportJob instead.
    page_start: Mapped[int | None] = mapped_column(Integer, nullable=True)
    page_end: Mapped[int | None] = mapped_column(Integer, nullable=True)
    inventory_metadata: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    source_path: Mapped[str] = mapped_column(Text)
    rights_status: Mapped[str] = mapped_column(String(32), default="unverified")
    rights_note: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    textbook: Mapped[Textbook] = relationship(back_populates="source_documents")
    import_jobs: Mapped[list["ImportJob"]] = relationship(back_populates="source_document")
    pages: Mapped[list["SourcePage"]] = relationship(back_populates="source_document", cascade="all, delete-orphan")


class ImportJob(Base):
    __tablename__ = "import_jobs"
    __table_args__ = (
        UniqueConstraint(
            "source_document_id", "page_start", "page_end",
            name="uq_import_jobs_document_range",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    source_document_id: Mapped[int] = mapped_column(ForeignKey("source_documents.id"), index=True)
    # The source file is identified by SourceDocument; each job owns one
    # requested processing range. These are nullable only for legacy jobs
    # created before range ownership moved from SourceDocument.
    page_start: Mapped[int | None] = mapped_column(Integer, nullable=True)
    page_end: Mapped[int | None] = mapped_column(Integer, nullable=True)
    state: Mapped[ImportState] = mapped_column(SqlEnum(ImportState), default=ImportState.queued)
    message: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    attempts: Mapped[int] = mapped_column(Integer, default=0)
    max_attempts: Mapped[int] = mapped_column(Integer, default=3)
    stage: Mapped[str] = mapped_column(String(32), default="registered")
    failure_stage: Mapped[str | None] = mapped_column(String(32), nullable=True)
    record_counts: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    quality_summary: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    worker_token: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    lease_expires_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True, index=True)
    source_document: Mapped[SourceDocument] = relationship(back_populates="import_jobs")


class SourcePage(Base):
    __tablename__ = "source_pages"
    __table_args__ = (UniqueConstraint("source_document_id", "pdf_page_number", name="uq_source_pages_document_page"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    source_document_id: Mapped[int] = mapped_column(ForeignKey("source_documents.id"), index=True)
    pdf_page_number: Mapped[int] = mapped_column(Integer)
    printed_page_number: Mapped[str | None] = mapped_column(String(32), nullable=True)
    raw_text: Mapped[str] = mapped_column(Text, default="")
    korean_character_count: Mapped[int] = mapped_column(Integer, default=0)
    vietnamese_character_count: Mapped[int] = mapped_column(Integer, default=0)
    image_count: Mapped[int] = mapped_column(Integer, default=0)
    needs_ocr: Mapped[bool] = mapped_column(default=False)
    extraction_method: Mapped[str] = mapped_column(String(32), default="pymupdf")
    source_document: Mapped[SourceDocument] = relationship(back_populates="pages")
    blocks: Mapped[list["SourceBlock"]] = relationship(back_populates="source_page", cascade="all, delete-orphan")


class SourceBlock(Base):
    __tablename__ = "source_blocks"
    id: Mapped[int] = mapped_column(primary_key=True)
    source_page_id: Mapped[int] = mapped_column(ForeignKey("source_pages.id"), index=True)
    block_index: Mapped[int] = mapped_column(Integer)
    text: Mapped[str] = mapped_column(Text, default="")
    x0: Mapped[float] = mapped_column()
    y0: Mapped[float] = mapped_column()
    x1: Mapped[float] = mapped_column()
    y1: Mapped[float] = mapped_column()
    is_header_footer_candidate: Mapped[bool] = mapped_column(default=False)
    source_page: Mapped[SourcePage] = relationship(back_populates="blocks")


class SourceSpan(Base):
    __tablename__ = "source_spans"
    id: Mapped[int] = mapped_column(primary_key=True)
    source_page_id: Mapped[int] = mapped_column(ForeignKey("source_pages.id"), index=True)
    source_block_id: Mapped[int | None] = mapped_column(ForeignKey("source_blocks.id"), nullable=True)
    label: Mapped[str] = mapped_column(String(64))
    raw_text: Mapped[str] = mapped_column(Text)
    normalized_text: Mapped[str] = mapped_column(Text)
    confidence: Mapped[float] = mapped_column(default=0.0)
    review_status: Mapped[str] = mapped_column(String(32), default="pending")
    extraction_version: Mapped[str] = mapped_column(String(64), default="raw-v1")
    version: Mapped[int] = mapped_column(Integer, default=1)


class Lesson(Base):
    __tablename__ = "lessons"
    id: Mapped[int] = mapped_column(primary_key=True)
    textbook_id: Mapped[int] = mapped_column(ForeignKey("textbooks.id"), index=True)
    ordinal: Mapped[int | None] = mapped_column(Integer, nullable=True)
    title: Mapped[str] = mapped_column(String(255))
    start_pdf_page: Mapped[int | None] = mapped_column(Integer, nullable=True)
    end_pdf_page: Mapped[int | None] = mapped_column(Integer, nullable=True)
    segmentation_method: Mapped[str] = mapped_column(String(64))
    review_status: Mapped[str] = mapped_column(String(32), default="pending")
    extraction_version: Mapped[str] = mapped_column(String(64), default="structured-v1")
    version: Mapped[int] = mapped_column(Integer, default=1)
    sections: Mapped[list["LessonSection"]] = relationship(back_populates="lesson", cascade="all, delete-orphan")


class LessonSection(Base):
    __tablename__ = "lesson_sections"
    __table_args__ = (UniqueConstraint("lesson_id", "section_type", "source_page_number", name="uq_lesson_sections_source"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    lesson_id: Mapped[int] = mapped_column(ForeignKey("lessons.id"), index=True)
    section_type: Mapped[str] = mapped_column(String(32))
    title: Mapped[str] = mapped_column(String(255))
    source_span_id: Mapped[int | None] = mapped_column(ForeignKey("source_spans.id"), nullable=True)
    source_page_number: Mapped[int] = mapped_column(Integer)
    review_status: Mapped[str] = mapped_column(String(32), default="pending")
    extraction_version: Mapped[str] = mapped_column(String(64), default="structured-v1")
    version: Mapped[int] = mapped_column(Integer, default=1)
    lesson: Mapped[Lesson] = relationship(back_populates="sections")


class Vocabulary(Base):
    __tablename__ = "vocabulary"
    __table_args__ = (
        UniqueConstraint("lesson_id", "normalized_headword", name="uq_vocabulary_lesson_headword"),
    )
    id: Mapped[int] = mapped_column(primary_key=True)
    lesson_id: Mapped[int | None] = mapped_column(ForeignKey("lessons.id"), nullable=True, index=True)
    headword: Mapped[str] = mapped_column(String(255), index=True)
    normalized_headword: Mapped[str] = mapped_column(String(255), index=True)
    extraction_method: Mapped[str] = mapped_column(String(64))
    confidence: Mapped[float] = mapped_column(default=0.0)
    review_status: Mapped[str] = mapped_column(String(32), default="pending")
    source_span_id: Mapped[int | None] = mapped_column(ForeignKey("source_spans.id"), nullable=True)
    extraction_version: Mapped[str] = mapped_column(String(64), default="structured-v1")
    version: Mapped[int] = mapped_column(Integer, default=1)
    content_origin: Mapped[str] = mapped_column(String(32), default="source_extracted")


class WordSense(Base):
    __tablename__ = "word_senses"
    id: Mapped[int] = mapped_column(primary_key=True)
    vocabulary_id: Mapped[int] = mapped_column(ForeignKey("vocabulary.id"), index=True)
    meaning_vi: Mapped[str] = mapped_column(Text)
    source_span_id: Mapped[int | None] = mapped_column(ForeignKey("source_spans.id"), nullable=True)
    review_status: Mapped[str] = mapped_column(String(32), default="pending")
    version: Mapped[int] = mapped_column(Integer, default=1)
    content_origin: Mapped[str] = mapped_column(String(32), default="source_extracted")


class GrammarPattern(Base):
    __tablename__ = "grammar_patterns"
    __table_args__ = (
        UniqueConstraint("lesson_id", "normalized_pattern", name="uq_grammar_lesson_pattern"),
    )
    id: Mapped[int] = mapped_column(primary_key=True)
    lesson_id: Mapped[int | None] = mapped_column(ForeignKey("lessons.id"), nullable=True, index=True)
    pattern: Mapped[str] = mapped_column(String(255))
    normalized_pattern: Mapped[str] = mapped_column(String(255))
    extraction_method: Mapped[str] = mapped_column(String(64))
    confidence: Mapped[float] = mapped_column(default=0.0)
    review_status: Mapped[str] = mapped_column(String(32), default="pending")
    explanation_vi: Mapped[str | None] = mapped_column(Text, nullable=True)
    usage_rules: Mapped[str | None] = mapped_column(Text, nullable=True)
    conjugation: Mapped[str | None] = mapped_column(Text, nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    source_span_id: Mapped[int | None] = mapped_column(ForeignKey("source_spans.id"), nullable=True)
    extraction_version: Mapped[str] = mapped_column(String(64), default="structured-v1")
    version: Mapped[int] = mapped_column(Integer, default=1)
    content_origin: Mapped[str] = mapped_column(String(32), default="source_extracted")


class SentenceIdentity(Base):
    __tablename__ = "sentence_identities"
    __table_args__ = (
        UniqueConstraint("owner_id", "normalized_text_ko", name="uq_sentence_identity_owner_text"),
    )
    id: Mapped[int] = mapped_column(primary_key=True)
    owner_id: Mapped[str] = mapped_column(String(128), index=True)
    canonical_text_ko: Mapped[str] = mapped_column(Text)
    normalized_text_ko: Mapped[str] = mapped_column(Text)


class Sentence(Base):
    __tablename__ = "sentences"
    id: Mapped[int] = mapped_column(primary_key=True)
    identity_id: Mapped[int | None] = mapped_column(ForeignKey("sentence_identities.id"), nullable=True, index=True)
    lesson_id: Mapped[int | None] = mapped_column(ForeignKey("lessons.id"), nullable=True, index=True)
    text_ko: Mapped[str] = mapped_column(Text)
    text_vi: Mapped[str | None] = mapped_column(Text, nullable=True)
    source_span_id: Mapped[int | None] = mapped_column(ForeignKey("source_spans.id"), nullable=True)
    review_status: Mapped[str] = mapped_column(String(32), default="pending")
    extraction_version: Mapped[str] = mapped_column(String(64), default="structured-v1")
    version: Mapped[int] = mapped_column(Integer, default=1)
    content_origin: Mapped[str] = mapped_column(String(32), default="source_extracted")
    vocabulary_items: Mapped[list["Vocabulary"]] = relationship(secondary=sentence_vocabulary)
    grammar_patterns: Mapped[list["GrammarPattern"]] = relationship(secondary=sentence_grammar_patterns)
    identity: Mapped["SentenceIdentity | None"] = relationship()


class Passage(Base):
    __tablename__ = "passages"
    id: Mapped[int] = mapped_column(primary_key=True)
    lesson_id: Mapped[int | None] = mapped_column(ForeignKey("lessons.id"), nullable=True, index=True)
    title: Mapped[str | None] = mapped_column(String(255), nullable=True)
    text: Mapped[str] = mapped_column(Text)
    source_span_id: Mapped[int | None] = mapped_column(ForeignKey("source_spans.id"), nullable=True)
    review_status: Mapped[str] = mapped_column(String(32), default="pending")
    extraction_version: Mapped[str] = mapped_column(String(64), default="structured-v1")
    version: Mapped[int] = mapped_column(Integer, default=1)
    content_origin: Mapped[str] = mapped_column(String(32), default="source_extracted")


class Dialogue(Base):
    __tablename__ = "dialogues"
    __table_args__ = (
        UniqueConstraint("lesson_id", "group_identifier", name="uq_dialogues_lesson_group"),
    )
    id: Mapped[int] = mapped_column(primary_key=True)
    lesson_id: Mapped[int | None] = mapped_column(ForeignKey("lessons.id"), nullable=True, index=True)
    source_span_id: Mapped[int | None] = mapped_column(ForeignKey("source_spans.id"), nullable=True)
    group_identifier: Mapped[str | None] = mapped_column(String(128), nullable=True)
    topic: Mapped[str | None] = mapped_column(String(255), nullable=True)
    content_origin: Mapped[str] = mapped_column(String(32), default="source_extracted")


class DialogueTurn(Base):
    __tablename__ = "dialogue_turns"
    __table_args__ = (
        UniqueConstraint("dialogue_id", "turn_index", name="uq_dialogue_turns_index"),
    )
    id: Mapped[int] = mapped_column(primary_key=True)
    dialogue_id: Mapped[int] = mapped_column(ForeignKey("dialogues.id"), index=True)
    turn_index: Mapped[int] = mapped_column(Integer)
    speaker: Mapped[str | None] = mapped_column(String(128), nullable=True)
    text: Mapped[str] = mapped_column(Text)
    text_vi: Mapped[str | None] = mapped_column(Text, nullable=True)
    source_span_id: Mapped[int | None] = mapped_column(ForeignKey("source_spans.id"), nullable=True)
    review_status: Mapped[str] = mapped_column(String(32), default="pending")
    version: Mapped[int] = mapped_column(Integer, default=1)
    content_origin: Mapped[str] = mapped_column(String(32), default="source_extracted")


class Exercise(Base):
    __tablename__ = "exercises"
    id: Mapped[int] = mapped_column(primary_key=True)
    lesson_id: Mapped[int | None] = mapped_column(ForeignKey("lessons.id"), nullable=True, index=True)
    prompt: Mapped[str] = mapped_column(Text)
    source_span_id: Mapped[int | None] = mapped_column(ForeignKey("source_spans.id"), nullable=True)
    review_status: Mapped[str] = mapped_column(String(32), default="pending")
    exercise_type: Mapped[str] = mapped_column(String(32), default="unknown")
    group_identifier: Mapped[str | None] = mapped_column(String(128), nullable=True)
    parent_exercise_id: Mapped[int | None] = mapped_column(ForeignKey("exercises.id"), nullable=True)
    passage_id: Mapped[int | None] = mapped_column(ForeignKey("passages.id"), nullable=True)
    listening_track_id: Mapped[int | None] = mapped_column(ForeignKey("listening_tracks.id"), nullable=True)
    extraction_version: Mapped[str] = mapped_column(String(64), default="structured-v1")
    version: Mapped[int] = mapped_column(Integer, default=1)
    content_origin: Mapped[str] = mapped_column(String(32), default="source_extracted")


class ExerciseOption(Base):
    __tablename__ = "exercise_options"
    __table_args__ = (
        UniqueConstraint("exercise_id", "option_index", name="uq_exercise_options_index"),
    )
    id: Mapped[int] = mapped_column(primary_key=True)
    exercise_id: Mapped[int] = mapped_column(ForeignKey("exercises.id"), index=True)
    option_index: Mapped[int] = mapped_column(Integer)
    text: Mapped[str] = mapped_column(Text)
    source_span_id: Mapped[int | None] = mapped_column(ForeignKey("source_spans.id"), nullable=True)
    review_status: Mapped[str] = mapped_column(String(32), default="pending")
    version: Mapped[int] = mapped_column(Integer, default=1)
    content_origin: Mapped[str] = mapped_column(String(32), default="source_extracted")


class ListeningTrack(Base):
    __tablename__ = "listening_tracks"
    __table_args__ = (
        UniqueConstraint("lesson_id", "track_identifier", name="uq_listening_tracks_identifier"),
    )
    id: Mapped[int] = mapped_column(primary_key=True)
    lesson_id: Mapped[int | None] = mapped_column(ForeignKey("lessons.id"), nullable=True, index=True)
    source_span_id: Mapped[int | None] = mapped_column(ForeignKey("source_spans.id"), nullable=True)
    asset_reference: Mapped[str | None] = mapped_column(Text, nullable=True)
    track_identifier: Mapped[str] = mapped_column(String(64), default="unknown")
    audio_status: Mapped[str] = mapped_column(String(32), default="missing")
    review_status: Mapped[str] = mapped_column(String(32), default="pending")
    extraction_version: Mapped[str] = mapped_column(String(64), default="structured-v1")
    version: Mapped[int] = mapped_column(Integer, default=1)
    content_origin: Mapped[str] = mapped_column(String(32), default="source_extracted")


class Transcript(Base):
    __tablename__ = "transcripts"
    id: Mapped[int] = mapped_column(primary_key=True)
    listening_track_id: Mapped[int] = mapped_column(ForeignKey("listening_tracks.id"), index=True)
    text: Mapped[str] = mapped_column(Text)
    source_span_id: Mapped[int | None] = mapped_column(ForeignKey("source_spans.id"), nullable=True)
    review_status: Mapped[str] = mapped_column(String(32), default="pending")
    version: Mapped[int] = mapped_column(Integer, default=1)
    content_origin: Mapped[str] = mapped_column(String(32), default="source_extracted")


class AnswerKey(Base):
    __tablename__ = "answer_keys"
    id: Mapped[int] = mapped_column(primary_key=True)
    exercise_id: Mapped[int] = mapped_column(ForeignKey("exercises.id"), index=True)
    answer_text: Mapped[str] = mapped_column(Text)
    source_span_id: Mapped[int] = mapped_column(ForeignKey("source_spans.id"))
    answer_index: Mapped[str | None] = mapped_column(String(64), nullable=True)
    review_status: Mapped[str] = mapped_column(String(32), default="pending")
    version: Mapped[int] = mapped_column(Integer, default=1)
    content_origin: Mapped[str] = mapped_column(String(32), default="source_extracted")


class ContentReview(Base):
    __tablename__ = "content_reviews"
    id: Mapped[int] = mapped_column(primary_key=True)
    entity_type: Mapped[str] = mapped_column(String(64))
    entity_id: Mapped[int] = mapped_column(Integer)
    status: Mapped[str] = mapped_column(String(32))
    note: Mapped[str | None] = mapped_column(Text, nullable=True)
    reviewer_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    source_span_id: Mapped[int | None] = mapped_column(ForeignKey("source_spans.id"), nullable=True)
    entity_version: Mapped[int | None] = mapped_column(Integer, nullable=True)
    reviewer_action: Mapped[str | None] = mapped_column(String(64), nullable=True)
    checks: Mapped[list | None] = mapped_column(JSON, nullable=True)
    change_set: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class ContentProvenance(Base):
    __tablename__ = "content_provenance"
    __table_args__ = (
        UniqueConstraint(
            "entity_type", "entity_id", "source_span_id", "extraction_method",
            "extraction_version", name="uq_content_provenance_source_method_version",
        ),
    )
    id: Mapped[int] = mapped_column(primary_key=True)
    entity_type: Mapped[str] = mapped_column(String(64))
    entity_id: Mapped[int] = mapped_column(Integer)
    source_span_id: Mapped[int] = mapped_column(ForeignKey("source_spans.id"), index=True)
    extraction_method: Mapped[str] = mapped_column(String(64))
    extraction_version: Mapped[str] = mapped_column(String(64), default="structured-v1")


class VocabularyProgress(Base):
    __tablename__ = "vocabulary_progress"
    __table_args__ = (
        UniqueConstraint("owner_id", "vocabulary_id", name="uq_vocabulary_progress_owner_item"),
    )
    id: Mapped[int] = mapped_column(primary_key=True)
    owner_id: Mapped[str] = mapped_column(String(128), index=True)
    vocabulary_id: Mapped[int] = mapped_column(ForeignKey("vocabulary.id"), index=True)
    status: Mapped[str] = mapped_column(String(32), default="new")
    repetitions: Mapped[int] = mapped_column(Integer, default=0)
    interval_days: Mapped[int] = mapped_column(Integer, default=0)
    next_review_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    last_reviewed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)


class StudyAttempt(Base):
    __tablename__ = "study_attempts"
    id: Mapped[int] = mapped_column(primary_key=True)
    owner_id: Mapped[str] = mapped_column(String(128), index=True)
    vocabulary_id: Mapped[int | None] = mapped_column(ForeignKey("vocabulary.id"), nullable=True, index=True)
    exercise_id: Mapped[int | None] = mapped_column(ForeignKey("exercises.id"), nullable=True, index=True)
    response: Mapped[str] = mapped_column(Text)
    correct: Mapped[bool | None] = mapped_column(nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class LessonProgress(Base):
    __tablename__ = "lesson_progress"
    __table_args__ = (
        UniqueConstraint("owner_id", "lesson_id", name="uq_lesson_progress_owner_lesson"),
    )
    id: Mapped[int] = mapped_column(primary_key=True)
    owner_id: Mapped[str] = mapped_column(String(128), index=True)
    lesson_id: Mapped[int] = mapped_column(ForeignKey("lessons.id"), index=True)
    status: Mapped[str] = mapped_column(String(32), default="not_started")
    completed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    last_opened_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)


class GrammarNote(Base):
    __tablename__ = "grammar_notes"
    __table_args__ = (
        UniqueConstraint("owner_id", "grammar_pattern_id", name="uq_grammar_notes_owner_pattern"),
    )
    id: Mapped[int] = mapped_column(primary_key=True)
    owner_id: Mapped[str] = mapped_column(String(128), index=True)
    grammar_pattern_id: Mapped[int] = mapped_column(ForeignKey("grammar_patterns.id"), index=True)
    note: Mapped[str] = mapped_column(Text)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
