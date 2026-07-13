"""poster archive: extended metadata, link history, needs_changes status

Revision ID: 0008
Revises: 0007
Create Date: 2026-07-13

Adds the metadata/duplicate-detection/Dropbox-link-health fields from the
Phase 2B spec: campaign_name, government_department, version, source,
needs_review, dropbox_link_broken, dropbox_last_verified_at on `posters`,
a new `poster_link_history` table, and a `needs_changes` value on the
existing PosterStatus enum (0006's "posterstatus" type).

All-additive: every new poster column is nullable (or boolean with a
server_default), no existing column or table is altered destructively,
and no backfill is attempted here - see 0002/0006's matching reasoning
for why heavy backfill work belongs in a separate maintenance script, not
inline in a migration.
"""
from alembic import op
import sqlalchemy as sa

revision = "0008"
down_revision = "0007"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("posters", sa.Column("campaign_name", sa.String(256), nullable=True))
    op.add_column("posters", sa.Column("government_department", sa.String(256), nullable=True))
    op.add_column("posters", sa.Column("version", sa.String(32), nullable=True))
    op.add_column("posters", sa.Column("source", sa.String(32), nullable=True))
    op.add_column("posters", sa.Column("needs_review", sa.Boolean, nullable=False, server_default=sa.false()))
    op.add_column("posters", sa.Column("dropbox_link_broken", sa.Boolean, nullable=True))
    op.add_column("posters", sa.Column("dropbox_last_verified_at", sa.DateTime, nullable=True))

    op.create_index("ix_posters_campaign_name", "posters", ["campaign_name"])
    op.create_index("ix_posters_government_department", "posters", ["government_department"])
    op.create_index("ix_posters_source", "posters", ["source"])
    op.create_index("ix_posters_needs_review", "posters", ["needs_review"])
    op.create_index("ix_posters_dropbox_link_broken", "posters", ["dropbox_link_broken"])

    # SQLite's ALTER TYPE has no equivalent for adding an enum value -
    # since Enum degrades to a plain VARCHAR + CHECK constraint there (see
    # 0002/0006's matching comment), a new value just needs the CHECK
    # constraint relaxed, which batch mode handles; PostgreSQL needs an
    # explicit ALTER TYPE ... ADD VALUE, which cannot run inside the same
    # transaction as other DDL in some driver configurations, so it's
    # guarded to only run there.
    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        op.execute("ALTER TYPE posterstatus ADD VALUE IF NOT EXISTS 'NEEDS_CHANGES'")

    op.create_table(
        "poster_link_history",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("poster_id", sa.String(36), sa.ForeignKey("posters.id"), nullable=False, index=True),
        sa.Column("old_url", sa.String(1024), nullable=True),
        sa.Column("new_url", sa.String(1024), nullable=True),
        sa.Column("changed_by", sa.String(128), nullable=True),
        sa.Column("changed_at", sa.DateTime, nullable=False),
    )
    op.create_index("ix_poster_link_history_changed_at", "poster_link_history", ["changed_at"])


def downgrade() -> None:
    op.drop_index("ix_poster_link_history_changed_at", table_name="poster_link_history")
    op.drop_table("poster_link_history")

    # Postgres enums can't drop a single value without recreating the type
    # (which every row using it would need remapped) - left in place on
    # downgrade, matching the "additive, no data loss" policy; a poster
    # already in needs_changes status simply keeps a value the older
    # PosterStatus Python enum wouldn't recognise, which only matters if
    # this specific downgrade path is actually exercised in production.

    op.drop_index("ix_posters_dropbox_link_broken", table_name="posters")
    op.drop_index("ix_posters_needs_review", table_name="posters")
    op.drop_index("ix_posters_source", table_name="posters")
    op.drop_index("ix_posters_government_department", table_name="posters")
    op.drop_index("ix_posters_campaign_name", table_name="posters")

    with op.batch_alter_table("posters") as batch_op:
        batch_op.drop_column("dropbox_last_verified_at")
        batch_op.drop_column("dropbox_link_broken")
        batch_op.drop_column("needs_review")
        batch_op.drop_column("source")
        batch_op.drop_column("version")
        batch_op.drop_column("government_department")
        batch_op.drop_column("campaign_name")
