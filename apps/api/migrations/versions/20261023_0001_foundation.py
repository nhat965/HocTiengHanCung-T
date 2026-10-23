"""phase 1 foundation schema

Revision ID: 20261023_0001
Revises:
Create Date: 2026-10-23
"""
from alembic import op
import sqlalchemy as sa


revision = "20261023_0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "textbooks",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("level", sa.String(length=64), nullable=False),
        sa.Column("volume_number", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("volume_number", name="uq_textbooks_volume_number"),
    )
    op.create_table(
        "source_documents",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("textbook_id", sa.Integer(), nullable=False),
        sa.Column("filename", sa.String(length=512), nullable=False),
        sa.Column("sha256", sa.String(length=64), nullable=False),
        sa.Column("page_count", sa.Integer(), nullable=True),
        sa.Column("source_path", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["textbook_id"], ["textbooks.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("sha256", name="uq_source_documents_sha256"),
    )
    op.create_index("ix_source_documents_textbook_id", "source_documents", ["textbook_id"])
    op.create_table(
        "import_jobs",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("source_document_id", sa.Integer(), nullable=False),
        sa.Column("state", sa.Enum("queued", "extracting", "needs_review", "completed", "failed", name="importstate"), nullable=False),
        sa.Column("message", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["source_document_id"], ["source_documents.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_import_jobs_source_document_id", "import_jobs", ["source_document_id"])


def downgrade() -> None:
    op.drop_index("ix_import_jobs_source_document_id", table_name="import_jobs")
    op.drop_table("import_jobs")
    op.drop_index("ix_source_documents_textbook_id", table_name="source_documents")
    op.drop_table("source_documents")
    op.drop_table("textbooks")
