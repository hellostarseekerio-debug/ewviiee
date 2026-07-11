"""security, privacy, approval workflow and version history

Revision ID: 0002
Revises: 0001
Create Date: 2026-07-11

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None

# On PostgreSQL, an enum is its own schema object (CREATE TYPE ... AS ENUM)
# that a column merely references by name. op.create_table() emits that
# CREATE TYPE automatically as part of building the table, but a bare
# op.add_column() does not - it only knows how to reference an
# already-existing type, which is why the plain `sa.Enum(...)` column
# below failed with "type approvalstatus does not exist" on a fresh
# Postgres database (SQLite has no native enum type, so it never surfaced
# there - Enum degrades to a VARCHAR + CHECK constraint instead).
# create_type=False so this Column definition never tries to (re-)create
# the type itself - creation is handled explicitly, once, below.
approval_status_enum = postgresql.ENUM(
    "PENDING", "APPROVED", "REJECTED", name="approvalstatus", create_type=False
)


def upgrade() -> None:
    # checkfirst=True makes this safe to re-run (e.g. a retried deploy
    # after a partial failure) without erroring on a type that already
    # exists. On SQLite this is a no-op - it degrades to a plain
    # CHECK-constrained column with no separate type to create.
    approval_status_enum.create(op.get_bind(), checkfirst=True)

    # --- Documents: approval workflow + soft delete -------------------------
    op.add_column(
        "documents",
        sa.Column(
            "approval_status",
            approval_status_enum,
            nullable=False,
            server_default="PENDING",
        ),
    )
    op.add_column("documents", sa.Column("reviewed_by", sa.String(128), nullable=True))
    op.add_column("documents", sa.Column("reviewed_at", sa.DateTime, nullable=True))
    op.add_column("documents", sa.Column("review_notes", sa.Text, nullable=True))
    op.add_column(
        "documents", sa.Column("is_deleted", sa.Boolean, nullable=False, server_default=sa.false())
    )
    op.add_column("documents", sa.Column("deleted_at", sa.DateTime, nullable=True))
    op.add_column("documents", sa.Column("deleted_by", sa.String(128), nullable=True))
    op.create_index("ix_documents_approval_status", "documents", ["approval_status"])
    op.create_index("ix_documents_is_deleted", "documents", ["is_deleted"])

    # --- Users: account lockout ----------------------------------------------
    op.add_column(
        "users", sa.Column("failed_login_attempts", sa.Integer, nullable=False, server_default="0")
    )
    op.add_column("users", sa.Column("locked_until", sa.DateTime, nullable=True))
    op.add_column("users", sa.Column("last_login_at", sa.DateTime, nullable=True))
    op.add_column("users", sa.Column("password_changed_at", sa.DateTime, nullable=True))

    # --- Document version history --------------------------------------------
    op.create_table(
        "document_versions",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("document_id", sa.String(36), sa.ForeignKey("documents.id"), index=True),
        sa.Column("version_number", sa.Integer, nullable=False),
        sa.Column("file_path", sa.String(1024), nullable=False),
        sa.Column("checksum_sha256", sa.String(64), nullable=True),
        sa.Column("created_by", sa.String(128), nullable=True),
        sa.Column("notes", sa.Text, nullable=True),
        sa.Column("created_at", sa.DateTime, nullable=False),
    )

    # --- Admin-configurable runtime settings (cloud-AI kill switch etc.) ----
    op.create_table(
        "system_settings",
        sa.Column("key", sa.String(128), primary_key=True),
        sa.Column("value", sa.Text, nullable=False),
        sa.Column("updated_by", sa.String(128), nullable=True),
        sa.Column("updated_at", sa.DateTime, nullable=False),
    )

    # --- AI usage audit trail (metadata only, never content) ----------------
    op.create_table(
        "ai_usage_logs",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("provider", sa.String(64), nullable=False, index=True),
        sa.Column("operation", sa.String(64), nullable=False),
        sa.Column("is_cloud_provider", sa.Boolean, nullable=False, server_default=sa.false()),
        sa.Column("document_id", sa.String(36), nullable=True, index=True),
        sa.Column("success", sa.Boolean, nullable=False, server_default=sa.true()),
        sa.Column("duration_ms", sa.Integer, nullable=True),
        sa.Column("created_at", sa.DateTime, nullable=False, index=True),
    )


def downgrade() -> None:
    op.drop_table("ai_usage_logs")
    op.drop_table("system_settings")
    op.drop_table("document_versions")

    op.drop_column("users", "password_changed_at")
    op.drop_column("users", "last_login_at")
    op.drop_column("users", "locked_until")
    op.drop_column("users", "failed_login_attempts")

    op.drop_index("ix_documents_is_deleted", table_name="documents")
    op.drop_index("ix_documents_approval_status", table_name="documents")
    op.drop_column("documents", "deleted_by")
    op.drop_column("documents", "deleted_at")
    op.drop_column("documents", "is_deleted")
    op.drop_column("documents", "review_notes")
    op.drop_column("documents", "reviewed_at")
    op.drop_column("documents", "reviewed_by")
    op.drop_column("documents", "approval_status")

    # Drop the enum type itself only after every column referencing it is
    # gone - Postgres refuses to drop a type still in use.
    approval_status_enum.drop(op.get_bind(), checkfirst=True)
