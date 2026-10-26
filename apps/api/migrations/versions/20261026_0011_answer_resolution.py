"""Add source-backed answer resolution contexts and candidates.

Revision ID: 20261026_0011
Revises: 20261024_0010
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "20261026_0011"
down_revision: Union[str, None] = "20261024_0010"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "exercise_answer_contexts",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("source_document_id", sa.Integer(), nullable=False),
        sa.Column("exercise_id", sa.Integer(), nullable=False),
        sa.Column("volume_number", sa.Integer(), nullable=False),
        sa.Column("lesson_number", sa.Integer(), nullable=False),
        sa.Column("skill_section", sa.String(length=64), nullable=False),
        sa.Column("exercise_group", sa.String(length=64), nullable=False),
        sa.Column("question_number", sa.String(length=64), nullable=False),
        sa.Column("compound_key", sa.String(length=384), nullable=False),
        sa.Column("question_source_span_id", sa.Integer(), nullable=False),
        sa.Column("review_status", sa.String(length=32), nullable=False, server_default="extracted"),
        sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("content_origin", sa.String(length=32), nullable=False, server_default="source_extracted"),
        sa.ForeignKeyConstraint(["exercise_id"], ["exercises.id"]),
        sa.ForeignKeyConstraint(["question_source_span_id"], ["source_spans.id"]),
        sa.ForeignKeyConstraint(["source_document_id"], ["source_documents.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("exercise_id", name="uq_exercise_answer_contexts_exercise"),
        sa.UniqueConstraint("source_document_id", "compound_key", name="uq_exercise_answer_contexts_document_key"),
    )
    op.create_index("ix_exercise_answer_contexts_source_document_id", "exercise_answer_contexts", ["source_document_id"])
    op.create_index("ix_exercise_answer_contexts_exercise_id", "exercise_answer_contexts", ["exercise_id"])
    op.create_index("ix_exercise_answer_contexts_compound_key", "exercise_answer_contexts", ["compound_key"])
    op.create_table(
        "answer_resolution_candidates",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("owner_id", sa.String(length=128), nullable=False),
        sa.Column("source_document_id", sa.Integer(), nullable=False),
        sa.Column("question_context_id", sa.Integer(), nullable=True),
        sa.Column("volume_number", sa.Integer(), nullable=True),
        sa.Column("lesson_number", sa.Integer(), nullable=True),
        sa.Column("skill_section", sa.String(length=64), nullable=True),
        sa.Column("exercise_group", sa.String(length=64), nullable=True),
        sa.Column("question_number", sa.String(length=64), nullable=True),
        sa.Column("compound_key", sa.String(length=384), nullable=True),
        sa.Column("answer_text", sa.Text(), nullable=False),
        sa.Column("answer_source_span_id", sa.Integer(), nullable=True),
        sa.Column("status", sa.String(length=32), nullable=False, server_default="extracted"),
        sa.Column("match_reason", sa.Text(), nullable=True),
        sa.Column("reviewer_note", sa.Text(), nullable=True),
        sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("content_origin", sa.String(length=32), nullable=False, server_default="source_extracted"),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["answer_source_span_id"], ["source_spans.id"]),
        sa.ForeignKeyConstraint(["question_context_id"], ["exercise_answer_contexts.id"]),
        sa.ForeignKeyConstraint(["source_document_id"], ["source_documents.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("source_document_id", "compound_key", "answer_source_span_id", "answer_text", name="uq_answer_resolution_candidates_source_key_text"),
    )
    op.create_index("ix_answer_resolution_candidates_owner_id", "answer_resolution_candidates", ["owner_id"])
    op.create_index("ix_answer_resolution_candidates_source_document_id", "answer_resolution_candidates", ["source_document_id"])
    op.create_index("ix_answer_resolution_candidates_question_context_id", "answer_resolution_candidates", ["question_context_id"])
    op.create_index("ix_answer_resolution_candidates_compound_key", "answer_resolution_candidates", ["compound_key"])
    op.create_index("ix_answer_resolution_candidates_status", "answer_resolution_candidates", ["status"])


def downgrade() -> None:
    op.drop_table("answer_resolution_candidates")
    op.drop_table("exercise_answer_contexts")
