"""Store structured human correction details in review history.

Revision ID: 20261024_0009
Revises: 20261024_0008
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "20261024_0009"
down_revision: Union[str, None] = "20261024_0008"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table("content_reviews") as batch:
        batch.add_column(sa.Column("change_set", sa.JSON(), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("content_reviews") as batch:
        batch.drop_column("change_set")
