"""private pilot inventory, review evidence, and learning progress

Revision ID: 20261024_0006
Revises: 20261024_0005
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "20261024_0006"
down_revision: Union[str, None] = "20261024_0005"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_ORIGIN_TABLES = (
    "vocabulary", "word_senses", "grammar_patterns", "sentences", "passages",
    "dialogues", "dialogue_turns", "exercises", "exercise_options",
    "listening_tracks", "transcripts", "answer_keys",
)


def upgrade() -> None:
    with op.batch_alter_table("source_documents") as batch:
        batch.add_column(sa.Column("file_size", sa.BigInteger(), nullable=True))
        batch.add_column(sa.Column("page_start", sa.Integer(), nullable=True))
        batch.add_column(sa.Column("page_end", sa.Integer(), nullable=True))
        batch.add_column(sa.Column("inventory_metadata", sa.JSON(), nullable=True))
    for table in _ORIGIN_TABLES:
        with op.batch_alter_table(table) as batch:
            batch.add_column(sa.Column(
                "content_origin", sa.String(length=32),
                server_default="source_extracted", nullable=False,
            ))
            if table == "exercise_options":
                batch.add_column(sa.Column("version", sa.Integer(), server_default="1", nullable=False))
    with op.batch_alter_table("content_reviews") as batch:
        batch.add_column(sa.Column("source_span_id", sa.Integer(), nullable=True))
        batch.add_column(sa.Column("entity_version", sa.Integer(), nullable=True))
        batch.add_column(sa.Column("reviewer_action", sa.String(length=64), nullable=True))
        batch.add_column(sa.Column("checks", sa.JSON(), nullable=True))
        batch.add_column(sa.Column("created_at", sa.DateTime(), nullable=True))
        batch.create_foreign_key(
            "fk_content_reviews_source_span_id_source_spans",
            "source_spans", ["source_span_id"], ["id"],
        )
    op.create_table(
        "vocabulary_progress",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("owner_id", sa.String(length=128), nullable=False),
        sa.Column("vocabulary_id", sa.Integer(), sa.ForeignKey("vocabulary.id"), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False, server_default="new"),
        sa.Column("repetitions", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("interval_days", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("next_review_at", sa.DateTime(), nullable=True),
        sa.Column("last_reviewed_at", sa.DateTime(), nullable=True),
        sa.UniqueConstraint("owner_id", "vocabulary_id", name="uq_vocabulary_progress_owner_item"),
    )
    op.create_index("ix_vocabulary_progress_owner_id", "vocabulary_progress", ["owner_id"])
    op.create_index("ix_vocabulary_progress_vocabulary_id", "vocabulary_progress", ["vocabulary_id"])
    op.create_table(
        "study_attempts",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("owner_id", sa.String(length=128), nullable=False),
        sa.Column("vocabulary_id", sa.Integer(), sa.ForeignKey("vocabulary.id"), nullable=True),
        sa.Column("exercise_id", sa.Integer(), sa.ForeignKey("exercises.id"), nullable=True),
        sa.Column("response", sa.Text(), nullable=False),
        sa.Column("correct", sa.Boolean(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )
    op.create_index("ix_study_attempts_owner_id", "study_attempts", ["owner_id"])
    op.create_index("ix_study_attempts_vocabulary_id", "study_attempts", ["vocabulary_id"])
    op.create_index("ix_study_attempts_exercise_id", "study_attempts", ["exercise_id"])
    op.create_table(
        "lesson_progress",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("owner_id", sa.String(length=128), nullable=False),
        sa.Column("lesson_id", sa.Integer(), sa.ForeignKey("lessons.id"), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False, server_default="not_started"),
        sa.Column("completed_at", sa.DateTime(), nullable=True),
        sa.UniqueConstraint("owner_id", "lesson_id", name="uq_lesson_progress_owner_lesson"),
    )
    op.create_index("ix_lesson_progress_owner_id", "lesson_progress", ["owner_id"])
    op.create_index("ix_lesson_progress_lesson_id", "lesson_progress", ["lesson_id"])


def downgrade() -> None:
    op.drop_index("ix_lesson_progress_lesson_id", table_name="lesson_progress")
    op.drop_index("ix_lesson_progress_owner_id", table_name="lesson_progress")
    op.drop_table("lesson_progress")
    op.drop_index("ix_study_attempts_exercise_id", table_name="study_attempts")
    op.drop_index("ix_study_attempts_vocabulary_id", table_name="study_attempts")
    op.drop_index("ix_study_attempts_owner_id", table_name="study_attempts")
    op.drop_table("study_attempts")
    op.drop_index("ix_vocabulary_progress_vocabulary_id", table_name="vocabulary_progress")
    op.drop_index("ix_vocabulary_progress_owner_id", table_name="vocabulary_progress")
    op.drop_table("vocabulary_progress")
    with op.batch_alter_table("content_reviews") as batch:
        batch.drop_constraint("fk_content_reviews_source_span_id_source_spans", type_="foreignkey")
        for column in ("created_at", "checks", "reviewer_action", "entity_version", "source_span_id"):
            batch.drop_column(column)
    for table in reversed(_ORIGIN_TABLES):
        with op.batch_alter_table(table) as batch:
            if table == "exercise_options":
                batch.drop_column("version")
            batch.drop_column("content_origin")
    with op.batch_alter_table("source_documents") as batch:
        for column in ("inventory_metadata", "page_end", "page_start", "file_size"):
            batch.drop_column(column)
