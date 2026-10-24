"""Add ownership leases for concurrent import workers.

Revision ID: 20261024_0010
Revises: 20261024_0009
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "20261024_0010"
down_revision: Union[str, None] = "20261024_0009"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table("import_jobs") as batch:
        batch.add_column(sa.Column("worker_token", sa.String(length=64), nullable=True))
        batch.add_column(sa.Column("lease_expires_at", sa.DateTime(), nullable=True))
        batch.create_index("ix_import_jobs_worker_token", ["worker_token"], unique=False)
        batch.create_index("ix_import_jobs_lease_expires_at", ["lease_expires_at"], unique=False)


def downgrade() -> None:
    with op.batch_alter_table("import_jobs") as batch:
        batch.drop_index("ix_import_jobs_lease_expires_at")
        batch.drop_index("ix_import_jobs_worker_token")
        batch.drop_column("lease_expires_at")
        batch.drop_column("worker_token")
