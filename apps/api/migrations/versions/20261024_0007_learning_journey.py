"""Persist lesson resume state and learner grammar notes.

Revision ID: 20261024_0007
Revises: 20261024_0006
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "20261024_0007"
down_revision: Union[str, None] = "20261024_0006"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table("lesson_progress") as batch:
        batch.add_column(sa.Column("last_opened_at", sa.DateTime(), nullable=True))
    op.create_table(
        "grammar_notes",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("owner_id", sa.String(length=128), nullable=False),
        sa.Column("grammar_pattern_id", sa.Integer(), sa.ForeignKey("grammar_patterns.id"), nullable=False),
        sa.Column("note", sa.Text(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.UniqueConstraint("owner_id", "grammar_pattern_id", name="uq_grammar_notes_owner_pattern"),
    )
    op.create_index("ix_grammar_notes_owner_id", "grammar_notes", ["owner_id"])
    op.create_index("ix_grammar_notes_grammar_pattern_id", "grammar_notes", ["grammar_pattern_id"])


def downgrade() -> None:
    op.drop_index("ix_grammar_notes_grammar_pattern_id", table_name="grammar_notes")
    op.drop_index("ix_grammar_notes_owner_id", table_name="grammar_notes")
    op.drop_table("grammar_notes")
    with op.batch_alter_table("lesson_progress") as batch:
        batch.drop_column("last_opened_at")
