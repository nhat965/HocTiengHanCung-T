"""Add learner interaction configuration to exercises.

Revision ID: 20261026_0012
Revises: 20261026_0011
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "20261026_0012"
down_revision: Union[str, None] = "20261026_0011"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "exercises",
        sa.Column("interaction_config", sa.JSON(), nullable=False, server_default=sa.text("'{}'")),
    )


def downgrade() -> None:
    op.drop_column("exercises", "interaction_config")
