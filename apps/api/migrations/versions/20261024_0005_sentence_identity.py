"""separate sentence identity from source occurrence

Revision ID: 20261024_0005
Revises: 20261023_0004
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "20261024_0005"
down_revision: Union[str, None] = "20261023_0004"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "sentence_identities",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("owner_id", sa.String(length=128), nullable=False),
        sa.Column("canonical_text_ko", sa.Text(), nullable=False),
        sa.Column("normalized_text_ko", sa.Text(), nullable=False),
        sa.UniqueConstraint("owner_id", "normalized_text_ko", name="uq_sentence_identity_owner_text"),
    )
    op.create_index("ix_sentence_identities_owner_id", "sentence_identities", ["owner_id"])
    with op.batch_alter_table("sentences") as batch:
        batch.add_column(sa.Column("identity_id", sa.Integer(), nullable=True))
        batch.create_foreign_key(
            "fk_sentences_identity_id_sentence_identities",
            "sentence_identities", ["identity_id"], ["id"],
        )
        batch.create_index("ix_sentences_identity_id", ["identity_id"])


def downgrade() -> None:
    with op.batch_alter_table("sentences") as batch:
        batch.drop_index("ix_sentences_identity_id")
        batch.drop_constraint("fk_sentences_identity_id_sentence_identities", type_="foreignkey")
        batch.drop_column("identity_id")
    op.drop_index("ix_sentence_identities_owner_id", table_name="sentence_identities")
    op.drop_table("sentence_identities")
