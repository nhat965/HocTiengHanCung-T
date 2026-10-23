"""Track structured extraction stages and outcomes.

Revision ID: 20261023_0004
Revises: 20261023_0003
"""
from alembic import op
import sqlalchemy as sa


revision = "20261023_0004"
down_revision = "20261023_0003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("import_jobs") as batch:
        batch.add_column(sa.Column("stage", sa.String(32), nullable=False, server_default="registered"))
        batch.add_column(sa.Column("failure_stage", sa.String(32), nullable=True))
        batch.add_column(sa.Column("record_counts", sa.JSON(), nullable=True))
        batch.add_column(sa.Column("quality_summary", sa.JSON(), nullable=True))
    for table, name, columns in (
        ("vocabulary", "uq_vocabulary_lesson_headword", ["lesson_id", "normalized_headword"]),
        ("grammar_patterns", "uq_grammar_lesson_pattern", ["lesson_id", "normalized_pattern"]),
        ("dialogues", "uq_dialogues_lesson_group", ["lesson_id", "group_identifier"]),
        ("dialogue_turns", "uq_dialogue_turns_index", ["dialogue_id", "turn_index"]),
        ("exercise_options", "uq_exercise_options_index", ["exercise_id", "option_index"]),
        ("listening_tracks", "uq_listening_tracks_identifier", ["lesson_id", "track_identifier"]),
        (
            "content_provenance",
            "uq_content_provenance_source_method_version",
            ["entity_type", "entity_id", "source_span_id", "extraction_method", "extraction_version"],
        ),
    ):
        op.create_index(name, table, columns, unique=True)


def downgrade() -> None:
    for table, name in (
        ("content_provenance", "uq_content_provenance_source_method_version"),
        ("listening_tracks", "uq_listening_tracks_identifier"),
        ("exercise_options", "uq_exercise_options_index"),
        ("dialogue_turns", "uq_dialogue_turns_index"),
        ("dialogues", "uq_dialogues_lesson_group"),
        ("grammar_patterns", "uq_grammar_lesson_pattern"),
        ("vocabulary", "uq_vocabulary_lesson_headword"),
    ):
        op.drop_index(name, table_name=table)
    with op.batch_alter_table("import_jobs") as batch:
        batch.drop_column("quality_summary")
        batch.drop_column("record_counts")
        batch.drop_column("failure_stage")
        batch.drop_column("stage")
