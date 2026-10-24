"""Store PDF page ranges on individual import jobs.

Revision ID: 20261024_0008
Revises: 20261024_0007
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "20261024_0008"
down_revision: Union[str, None] = "20261024_0007"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table("import_jobs") as batch:
        batch.add_column(sa.Column("page_start", sa.Integer(), nullable=True))
        batch.add_column(sa.Column("page_end", sa.Integer(), nullable=True))

    # Preserve the range recorded by the previous schema on the first job for
    # each document. Legacy jobs without a range remain full-document jobs and
    # are handled by the worker fallback.
    bind = op.get_bind()
    bind.execute(sa.text(
        """
        UPDATE import_jobs
        SET page_start = (
                SELECT page_start FROM source_documents
                WHERE source_documents.id = import_jobs.source_document_id
            ),
            page_end = (
                SELECT page_end FROM source_documents
                WHERE source_documents.id = import_jobs.source_document_id
            )
        WHERE id IN (
            SELECT MIN(first_job.id)
            FROM import_jobs AS first_job
            GROUP BY first_job.source_document_id
        )
        AND page_start IS NULL
        AND page_end IS NULL
        """
    ))

    with op.batch_alter_table("import_jobs") as batch:
        batch.create_unique_constraint(
            "uq_import_jobs_document_range",
            ["source_document_id", "page_start", "page_end"],
        )


def downgrade() -> None:
    with op.batch_alter_table("import_jobs") as batch:
        batch.drop_constraint("uq_import_jobs_document_range", type_="unique")
        batch.drop_column("page_end")
        batch.drop_column("page_start")
