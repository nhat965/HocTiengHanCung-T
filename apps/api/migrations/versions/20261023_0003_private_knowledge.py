"""Private ownership and versioned structured knowledge.

Revision ID: 20261023_0003
Revises: 20261023_0002
"""
from alembic import op
import sqlalchemy as sa


revision = "20261023_0003"
down_revision = "20261023_0002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("textbooks") as batch:
        batch.drop_constraint("uq_textbooks_volume_number", type_="unique")
        batch.add_column(sa.Column("owner_id", sa.String(128), nullable=False, server_default="local-owner"))
        batch.create_index("ix_textbooks_owner_id", ["owner_id"])
        batch.create_unique_constraint("uq_textbooks_owner_volume", ["owner_id", "volume_number"])

    with op.batch_alter_table("source_documents") as batch:
        batch.drop_constraint("uq_source_documents_sha256", type_="unique")
        batch.add_column(sa.Column("owner_id", sa.String(128), nullable=False, server_default="local-owner"))
        batch.add_column(sa.Column("rights_status", sa.String(32), nullable=False, server_default="unverified"))
        batch.add_column(sa.Column("rights_note", sa.Text(), nullable=True))
        batch.create_index("ix_source_documents_owner_id", ["owner_id"])
        batch.create_unique_constraint("uq_source_documents_owner_sha256", ["owner_id", "sha256"])

    columns = {
        "lessons": [
            sa.Column("extraction_version", sa.String(64), nullable=False, server_default="structured-v1"),
            sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
        ],
        "source_spans": [
            sa.Column("extraction_version", sa.String(64), nullable=False, server_default="raw-v1"),
            sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
        ],
        "vocabulary": [
            sa.Column("source_span_id", sa.Integer(), sa.ForeignKey("source_spans.id", name="fk_vocabulary_source_span")),
            sa.Column("extraction_version", sa.String(64), nullable=False, server_default="structured-v1"),
            sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
        ],
        "word_senses": [
            sa.Column("source_span_id", sa.Integer(), sa.ForeignKey("source_spans.id", name="fk_word_senses_source_span")),
            sa.Column("review_status", sa.String(32), nullable=False, server_default="pending"),
            sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
        ],
        "grammar_patterns": [
            sa.Column("explanation_vi", sa.Text()),
            sa.Column("usage_rules", sa.Text()),
            sa.Column("conjugation", sa.Text()),
            sa.Column("notes", sa.Text()),
            sa.Column("source_span_id", sa.Integer(), sa.ForeignKey("source_spans.id", name="fk_grammar_source_span")),
            sa.Column("extraction_version", sa.String(64), nullable=False, server_default="structured-v1"),
            sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
        ],
        "sentences": [
            sa.Column("review_status", sa.String(32), nullable=False, server_default="pending"),
            sa.Column("extraction_version", sa.String(64), nullable=False, server_default="structured-v1"),
            sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
        ],
        "passages": [
            sa.Column("source_span_id", sa.Integer(), sa.ForeignKey("source_spans.id", name="fk_passages_source_span")),
            sa.Column("review_status", sa.String(32), nullable=False, server_default="pending"),
            sa.Column("extraction_version", sa.String(64), nullable=False, server_default="structured-v1"),
            sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
        ],
        "dialogue_turns": [
            sa.Column("text_vi", sa.Text()),
            sa.Column("source_span_id", sa.Integer(), sa.ForeignKey("source_spans.id", name="fk_turns_source_span")),
            sa.Column("review_status", sa.String(32), nullable=False, server_default="pending"),
            sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
        ],
        "dialogues": [
            sa.Column("group_identifier", sa.String(128)),
            sa.Column("topic", sa.String(255)),
        ],
        "exercises": [
            sa.Column("exercise_type", sa.String(32), nullable=False, server_default="unknown"),
            sa.Column("group_identifier", sa.String(128)),
            sa.Column("parent_exercise_id", sa.Integer(), sa.ForeignKey("exercises.id", name="fk_exercises_parent")),
            sa.Column("passage_id", sa.Integer(), sa.ForeignKey("passages.id", name="fk_exercises_passage")),
            sa.Column("listening_track_id", sa.Integer(), sa.ForeignKey("listening_tracks.id", name="fk_exercises_track")),
            sa.Column("extraction_version", sa.String(64), nullable=False, server_default="structured-v1"),
            sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
        ],
        "exercise_options": [
            sa.Column("source_span_id", sa.Integer(), sa.ForeignKey("source_spans.id", name="fk_options_source_span")),
            sa.Column("review_status", sa.String(32), nullable=False, server_default="pending"),
        ],
        "listening_tracks": [
            sa.Column("track_identifier", sa.String(64), nullable=False, server_default="unknown"),
            sa.Column("audio_status", sa.String(32), nullable=False, server_default="missing"),
            sa.Column("review_status", sa.String(32), nullable=False, server_default="pending"),
            sa.Column("extraction_version", sa.String(64), nullable=False, server_default="structured-v1"),
            sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
        ],
        "transcripts": [
            sa.Column("source_span_id", sa.Integer(), sa.ForeignKey("source_spans.id", name="fk_transcripts_source_span")),
            sa.Column("review_status", sa.String(32), nullable=False, server_default="pending"),
            sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
        ],
        "answer_keys": [
            sa.Column("answer_index", sa.String(64)),
            sa.Column("review_status", sa.String(32), nullable=False, server_default="pending"),
            sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
        ],
        "content_reviews": [sa.Column("reviewer_id", sa.String(128))],
        "content_provenance": [
            sa.Column("extraction_version", sa.String(64), nullable=False, server_default="structured-v1"),
        ],
    }
    for table, table_columns in columns.items():
        with op.batch_alter_table(table) as batch:
            for column in table_columns:
                batch.add_column(column)

    op.create_table(
        "lesson_sections",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("lesson_id", sa.Integer(), sa.ForeignKey("lessons.id"), nullable=False),
        sa.Column("section_type", sa.String(32), nullable=False),
        sa.Column("title", sa.String(255), nullable=False),
        sa.Column("source_span_id", sa.Integer(), sa.ForeignKey("source_spans.id")),
        sa.Column("source_page_number", sa.Integer(), nullable=False),
        sa.Column("review_status", sa.String(32), nullable=False, server_default="pending"),
        sa.Column("extraction_version", sa.String(64), nullable=False, server_default="structured-v1"),
        sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
        sa.UniqueConstraint("lesson_id", "section_type", "source_page_number", name="uq_lesson_sections_source"),
    )
    op.create_index("ix_lesson_sections_lesson_id", "lesson_sections", ["lesson_id"])
    op.create_table(
        "sentence_vocabulary",
        sa.Column("sentence_id", sa.Integer(), sa.ForeignKey("sentences.id"), primary_key=True),
        sa.Column("vocabulary_id", sa.Integer(), sa.ForeignKey("vocabulary.id"), primary_key=True),
    )
    op.create_table(
        "sentence_grammar_patterns",
        sa.Column("sentence_id", sa.Integer(), sa.ForeignKey("sentences.id"), primary_key=True),
        sa.Column("grammar_pattern_id", sa.Integer(), sa.ForeignKey("grammar_patterns.id"), primary_key=True),
    )


def downgrade() -> None:
    op.drop_index("ix_lesson_sections_lesson_id", table_name="lesson_sections")
    op.drop_table("lesson_sections")
    op.drop_table("sentence_grammar_patterns")
    op.drop_table("sentence_vocabulary")
    drops = (
        ("content_provenance", ["extraction_version"]),
        ("content_reviews", ["reviewer_id"]),
        ("source_spans", ["version", "extraction_version"]),
        ("answer_keys", ["version", "review_status", "answer_index"]),
        ("transcripts", ["version", "review_status", "source_span_id"]),
        ("listening_tracks", ["version", "extraction_version", "review_status", "audio_status", "track_identifier"]),
        ("exercise_options", ["review_status", "source_span_id"]),
        ("exercises", ["version", "extraction_version", "listening_track_id", "passage_id", "parent_exercise_id", "group_identifier", "exercise_type"]),
        ("dialogue_turns", ["version", "review_status", "source_span_id", "text_vi"]),
        ("dialogues", ["topic", "group_identifier"]),
        ("passages", ["version", "extraction_version", "review_status", "source_span_id"]),
        ("sentences", ["version", "extraction_version", "review_status"]),
        ("grammar_patterns", ["version", "extraction_version", "source_span_id", "notes", "conjugation", "usage_rules", "explanation_vi"]),
        ("word_senses", ["version", "review_status", "source_span_id"]),
        ("vocabulary", ["version", "extraction_version", "source_span_id"]),
        ("lessons", ["version", "extraction_version"]),
    )
    for table, names in drops:
        with op.batch_alter_table(table) as batch:
            for name in names:
                batch.drop_column(name)

    with op.batch_alter_table("source_documents") as batch:
        batch.drop_constraint("uq_source_documents_owner_sha256", type_="unique")
        batch.drop_index("ix_source_documents_owner_id")
        batch.drop_column("rights_note")
        batch.drop_column("rights_status")
        batch.drop_column("owner_id")
        batch.create_unique_constraint("uq_source_documents_sha256", ["sha256"])

    with op.batch_alter_table("textbooks") as batch:
        batch.drop_constraint("uq_textbooks_owner_volume", type_="unique")
        batch.drop_index("ix_textbooks_owner_id")
        batch.drop_column("owner_id")
        batch.create_unique_constraint("uq_textbooks_volume_number", ["volume_number"])
