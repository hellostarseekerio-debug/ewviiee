"""metadata extraction engine v2: region/politicians/date_to/confidence

Revision ID: 0010
Revises: 0009
Create Date: 2026-07-13

Adds the fields the redesigned metadata extraction pipeline
(app/posters/parser.py, app/posters/estates.py) needs: `region` and
`politicians` (auto-filled from the resolved estate's metadata bundle),
`date_to` (date-range support), and `extraction_confidence`/
`extraction_sources` (per-field confidence/source, so a future UI can
show a warning icon on exactly the fields that were low-confidence or
AI-guessed). Also adds `metadata_extraction_cache`, the AI-fallback
result cache (app/posters/ai_fallback.py).

All-additive: every new poster column is nullable, no existing column or
table is altered destructively.
"""
from alembic import op
import sqlalchemy as sa

revision = "0010"
down_revision = "0009"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("posters", sa.Column("region", sa.String(64), nullable=True))
    op.add_column("posters", sa.Column("politicians", sa.JSON, nullable=True))
    op.add_column("posters", sa.Column("date_to", sa.DateTime, nullable=True))
    op.add_column("posters", sa.Column("extraction_confidence", sa.JSON, nullable=True))
    op.add_column("posters", sa.Column("extraction_sources", sa.JSON, nullable=True))
    op.create_index("ix_posters_region", "posters", ["region"])

    op.create_table(
        "metadata_extraction_cache",
        sa.Column("text_hash", sa.String(64), primary_key=True),
        sa.Column("result", sa.JSON, nullable=False),
        sa.Column("created_at", sa.DateTime, nullable=False),
    )
    op.create_index("ix_metadata_extraction_cache_created_at", "metadata_extraction_cache", ["created_at"])


def downgrade() -> None:
    op.drop_index("ix_metadata_extraction_cache_created_at", table_name="metadata_extraction_cache")
    op.drop_table("metadata_extraction_cache")

    op.drop_index("ix_posters_region", table_name="posters")
    with op.batch_alter_table("posters") as batch_op:
        batch_op.drop_column("extraction_sources")
        batch_op.drop_column("extraction_confidence")
        batch_op.drop_column("date_to")
        batch_op.drop_column("politicians")
        batch_op.drop_column("region")
