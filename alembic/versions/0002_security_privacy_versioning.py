"""security, privacy, approval workflow and version history

Revision ID: 0002
Revises: 0001
Create Date: 2026-07-11

"""
from alembic import op
import sqlalchemy as sa

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # --- Documents: approval workflow + soft delete -------------------------
    op.add_column(
        "documents",
        sa.Column(
            "approval_status",
            sa.Enum("PENDING", "APPROVED", "REJECTED", name="approvalstatus"),
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
