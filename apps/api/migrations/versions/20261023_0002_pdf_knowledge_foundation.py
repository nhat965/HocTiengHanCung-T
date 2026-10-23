"""PDF knowledge foundation

Revision ID: 20261023_0002
Revises: 20261023_0001
Create Date: 2026-10-23
"""
from alembic import op
import sqlalchemy as sa

revision = "20261023_0002"
down_revision = "20261023_0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    if op.get_bind().dialect.name == "postgresql":
        for value in ("registered", "extracted"):
            op.execute(f"ALTER TYPE importstate ADD VALUE IF NOT EXISTS '{value}'")
    op.add_column("import_jobs", sa.Column("attempts", sa.Integer(), nullable=False, server_default="0"))
    op.add_column("import_jobs", sa.Column("max_attempts", sa.Integer(), nullable=False, server_default="3"))
    op.create_table("source_pages", sa.Column("id", sa.Integer(), primary_key=True), sa.Column("source_document_id", sa.Integer(), sa.ForeignKey("source_documents.id"), nullable=False), sa.Column("pdf_page_number", sa.Integer(), nullable=False), sa.Column("printed_page_number", sa.String(32)), sa.Column("raw_text", sa.Text(), nullable=False), sa.Column("korean_character_count", sa.Integer(), nullable=False), sa.Column("vietnamese_character_count", sa.Integer(), nullable=False), sa.Column("image_count", sa.Integer(), nullable=False), sa.Column("needs_ocr", sa.Boolean(), nullable=False), sa.Column("extraction_method", sa.String(32), nullable=False), sa.UniqueConstraint("source_document_id", "pdf_page_number", name="uq_source_pages_document_page"))
    op.create_table("source_blocks", sa.Column("id", sa.Integer(), primary_key=True), sa.Column("source_page_id", sa.Integer(), sa.ForeignKey("source_pages.id"), nullable=False), sa.Column("block_index", sa.Integer(), nullable=False), sa.Column("text", sa.Text(), nullable=False), sa.Column("x0", sa.Float(), nullable=False), sa.Column("y0", sa.Float(), nullable=False), sa.Column("x1", sa.Float(), nullable=False), sa.Column("y1", sa.Float(), nullable=False), sa.Column("is_header_footer_candidate", sa.Boolean(), nullable=False))
    op.create_table("source_spans", sa.Column("id", sa.Integer(), primary_key=True), sa.Column("source_page_id", sa.Integer(), sa.ForeignKey("source_pages.id"), nullable=False), sa.Column("source_block_id", sa.Integer(), sa.ForeignKey("source_blocks.id")), sa.Column("label", sa.String(64), nullable=False), sa.Column("raw_text", sa.Text(), nullable=False), sa.Column("normalized_text", sa.Text(), nullable=False), sa.Column("confidence", sa.Float(), nullable=False), sa.Column("review_status", sa.String(32), nullable=False))
    op.create_table("lessons", sa.Column("id", sa.Integer(), primary_key=True), sa.Column("textbook_id", sa.Integer(), sa.ForeignKey("textbooks.id"), nullable=False), sa.Column("ordinal", sa.Integer()), sa.Column("title", sa.String(255), nullable=False), sa.Column("start_pdf_page", sa.Integer()), sa.Column("end_pdf_page", sa.Integer()), sa.Column("segmentation_method", sa.String(64), nullable=False), sa.Column("review_status", sa.String(32), nullable=False))
    for name, columns in {
        "vocabulary": [sa.Column("lesson_id", sa.Integer(), sa.ForeignKey("lessons.id")), sa.Column("headword", sa.String(255), nullable=False), sa.Column("normalized_headword", sa.String(255), nullable=False), sa.Column("extraction_method", sa.String(64), nullable=False), sa.Column("confidence", sa.Float(), nullable=False), sa.Column("review_status", sa.String(32), nullable=False)],
        "word_senses": [sa.Column("vocabulary_id", sa.Integer(), sa.ForeignKey("vocabulary.id"), nullable=False), sa.Column("meaning_vi", sa.Text(), nullable=False)],
        "grammar_patterns": [sa.Column("lesson_id", sa.Integer(), sa.ForeignKey("lessons.id")), sa.Column("pattern", sa.String(255), nullable=False), sa.Column("normalized_pattern", sa.String(255), nullable=False), sa.Column("extraction_method", sa.String(64), nullable=False), sa.Column("confidence", sa.Float(), nullable=False), sa.Column("review_status", sa.String(32), nullable=False)],
        "sentences": [sa.Column("lesson_id", sa.Integer(), sa.ForeignKey("lessons.id")), sa.Column("text_ko", sa.Text(), nullable=False), sa.Column("text_vi", sa.Text()), sa.Column("source_span_id", sa.Integer(), sa.ForeignKey("source_spans.id"))],
        "passages": [sa.Column("lesson_id", sa.Integer(), sa.ForeignKey("lessons.id")), sa.Column("title", sa.String(255)), sa.Column("text", sa.Text(), nullable=False)],
        "dialogues": [sa.Column("lesson_id", sa.Integer(), sa.ForeignKey("lessons.id")), sa.Column("source_span_id", sa.Integer(), sa.ForeignKey("source_spans.id"))],
        "dialogue_turns": [sa.Column("dialogue_id", sa.Integer(), sa.ForeignKey("dialogues.id"), nullable=False), sa.Column("turn_index", sa.Integer(), nullable=False), sa.Column("speaker", sa.String(128)), sa.Column("text", sa.Text(), nullable=False)],
        "exercises": [sa.Column("lesson_id", sa.Integer(), sa.ForeignKey("lessons.id")), sa.Column("prompt", sa.Text(), nullable=False), sa.Column("source_span_id", sa.Integer(), sa.ForeignKey("source_spans.id")), sa.Column("review_status", sa.String(32), nullable=False)],
        "exercise_options": [sa.Column("exercise_id", sa.Integer(), sa.ForeignKey("exercises.id"), nullable=False), sa.Column("option_index", sa.Integer(), nullable=False), sa.Column("text", sa.Text(), nullable=False)],
        "listening_tracks": [sa.Column("lesson_id", sa.Integer(), sa.ForeignKey("lessons.id")), sa.Column("source_span_id", sa.Integer(), sa.ForeignKey("source_spans.id")), sa.Column("asset_reference", sa.Text())],
        "transcripts": [sa.Column("listening_track_id", sa.Integer(), sa.ForeignKey("listening_tracks.id"), nullable=False), sa.Column("text", sa.Text(), nullable=False)],
        "answer_keys": [sa.Column("exercise_id", sa.Integer(), sa.ForeignKey("exercises.id"), nullable=False), sa.Column("answer_text", sa.Text(), nullable=False), sa.Column("source_span_id", sa.Integer(), sa.ForeignKey("source_spans.id"), nullable=False)],
        "content_reviews": [sa.Column("entity_type", sa.String(64), nullable=False), sa.Column("entity_id", sa.Integer(), nullable=False), sa.Column("status", sa.String(32), nullable=False), sa.Column("note", sa.Text())],
        "content_provenance": [sa.Column("entity_type", sa.String(64), nullable=False), sa.Column("entity_id", sa.Integer(), nullable=False), sa.Column("source_span_id", sa.Integer(), sa.ForeignKey("source_spans.id"), nullable=False), sa.Column("extraction_method", sa.String(64), nullable=False)],
    }.items():
        op.create_table(name, sa.Column("id", sa.Integer(), primary_key=True), *columns)


def downgrade() -> None:
    for name in ["content_provenance", "content_reviews", "answer_keys", "transcripts", "listening_tracks", "exercise_options", "exercises", "dialogue_turns", "dialogues", "passages", "sentences", "grammar_patterns", "word_senses", "vocabulary", "lessons", "source_spans", "source_blocks", "source_pages"]:
        op.drop_table(name)
    op.drop_column("import_jobs", "max_attempts")
    op.drop_column("import_jobs", "attempts")
