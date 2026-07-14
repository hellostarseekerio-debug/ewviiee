"""learned field corrections (parser self-improvement loop)

Revision ID: 0011
Revises: 0010
Create Date: 2026-07-14

Adds `learned_field_corrections`: when staff correct a low-confidence/
missing field on a poster (e.g. filling in the district for an estate
the parser recognised but couldn't place), the correction is remembered
here and consulted by future imports mentioning the same estate name -
see app/posters/corrections.py and app/posters/parser.py.

Purely additive - a new table, nothing existing touched.
"""
from alembic import op
import sqlalchemy as sa

revision = "0011"
down_revision = "0010"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "learned_field_corrections",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("key_type", sa.String(32), nullable=False),
        sa.Column("key_value", sa.String(256), nullable=False),
        sa.Column("field", sa.String(32), nullable=False),
        sa.Column("value", sa.String(256), nullable=False),
        sa.Column("corrected_by", sa.String(128), nullable=True),
        sa.Column("created_at", sa.DateTime, nullable=False),
        sa.Column("updated_at", sa.DateTime, nullable=False),
        sa.UniqueConstraint("key_type", "key_value", "field", name="uq_learned_correction_key"),
    )
    op.create_index("ix_learned_field_corrections_key_type", "learned_field_corrections", ["key_type"])
    op.create_index("ix_learned_field_corrections_key_value", "learned_field_corrections", ["key_value"])


def downgrade() -> None:
    op.drop_index("ix_learned_field_corrections_key_value", table_name="learned_field_corrections")
    op.drop_index("ix_learned_field_corrections_key_type", table_name="learned_field_corrections")
    op.drop_table("learned_field_corrections")
