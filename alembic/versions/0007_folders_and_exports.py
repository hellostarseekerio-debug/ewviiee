"""folders, starred items, export jobs

Revision ID: 0007
Revises: 0006
Create Date: 2026-07-13

Adds the generic, resource-agnostic folder system (app/folders/service.py)
plus two small supporting tables:
  - starred_items: per-user favorites, reusable across resource types.
  - export_jobs: tracks background ZIP exports (app/storage/archive_zip.py).

`posters.folder_id` is the only resource-side change in this migration -
nullable, so every existing poster is simply "unfiled" until either the
Year/Month/District/Estate auto-suggestion (app/folders/suggestions.py) or
a manual move assigns it one. No backfill is performed here deliberately:
retroactively auto-filing thousands of existing posters is a one-off
maintenance script, not migration logic (see 0002/0006's matching
reasoning about keeping heavy backfill work out of the migration itself).
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0007"
down_revision = "0006"
branch_labels = None
depends_on = None

export_job_status_enum = postgresql.ENUM(
    "PENDING", "RUNNING", "COMPLETED", "FAILED", name="exportjobstatus", create_type=False
)


def upgrade() -> None:
    op.create_table(
        "folders",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("parent_id", sa.String(36), sa.ForeignKey("folders.id"), nullable=True, index=True),
        sa.Column("path", sa.String(2048), nullable=False, index=True),
        sa.Column("depth", sa.Integer, nullable=False, server_default="0", index=True),
        sa.Column("created_by", sa.String(128), nullable=True),
        sa.Column("created_at", sa.DateTime, nullable=False),
        sa.Column("updated_at", sa.DateTime, nullable=False),
    )

    # batch_alter_table (not a plain op.add_column): SQLite can't ALTER a
    # constraint onto an existing table (no native ALTER TABLE ADD
    # CONSTRAINT), so adding a column with a foreign key requires the
    # "copy table, add column, swap in" batch strategy. Works identically
    # on PostgreSQL (batch mode there just emits a normal ALTER), so this
    # is the portable way to write it rather than a dialect-specific branch.
    with op.batch_alter_table("posters") as batch_op:
        # SQLite's batch mode rebuilds the whole table to apply the new
        # foreign key, which requires the constraint to have an explicit
        # name (unlike a plain CREATE TABLE, where an unnamed FK is fine).
        batch_op.add_column(
            sa.Column("folder_id", sa.String(36), sa.ForeignKey("folders.id", name="fk_posters_folder_id"), nullable=True)
        )
        batch_op.create_index("ix_posters_folder_id", ["folder_id"])

    op.create_table(
        "starred_items",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("user_id", sa.String(36), sa.ForeignKey("users.id"), nullable=False, index=True),
        sa.Column("resource_type", sa.String(32), nullable=False, index=True),
        sa.Column("resource_id", sa.String(36), nullable=False, index=True),
        sa.Column("created_at", sa.DateTime, nullable=False),
        sa.UniqueConstraint("user_id", "resource_type", "resource_id", name="uq_starred_item"),
    )

    export_job_status_enum.create(op.get_bind(), checkfirst=True)
    op.create_table(
        "export_jobs",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("resource_type", sa.String(32), nullable=False),
        sa.Column("status", export_job_status_enum, nullable=False, server_default="PENDING"),
        sa.Column("requested_by", sa.String(128), nullable=True),
        sa.Column("total_items", sa.Integer, nullable=False, server_default="0"),
        sa.Column("included_items", sa.Integer, nullable=False, server_default="0"),
        sa.Column("file_path", sa.String(1024), nullable=True),
        sa.Column("file_size_bytes", sa.Integer, nullable=True),
        sa.Column("error_message", sa.Text, nullable=True),
        sa.Column("created_at", sa.DateTime, nullable=False),
        sa.Column("completed_at", sa.DateTime, nullable=True),
    )
    op.create_index("ix_export_jobs_status", "export_jobs", ["status"])
    op.create_index("ix_export_jobs_created_at", "export_jobs", ["created_at"])


def downgrade() -> None:
    op.drop_index("ix_export_jobs_created_at", table_name="export_jobs")
    op.drop_index("ix_export_jobs_status", table_name="export_jobs")
    op.drop_table("export_jobs")
    export_job_status_enum.drop(op.get_bind(), checkfirst=True)

    op.drop_table("starred_items")

    with op.batch_alter_table("posters") as batch_op:
        batch_op.drop_index("ix_posters_folder_id")
        batch_op.drop_column("folder_id")

    op.drop_table("folders")
