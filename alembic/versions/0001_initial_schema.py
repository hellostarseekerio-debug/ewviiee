"""initial schema

Revision ID: 0001
Revises:
Create Date: 2026-07-11

"""
from alembic import op
import sqlalchemy as sa

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "documents",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("filename", sa.String(512), nullable=False),
        sa.Column("source_path", sa.String(1024), nullable=False),
        sa.Column("document_type", sa.String(128), nullable=True),
        sa.Column("workflow_name", sa.String(128), nullable=True, index=True),
        sa.Column(
            "status",
            sa.Enum(
                "IMPORTED", "CLASSIFIED", "OCR_DONE", "EXTRACTED", "VALIDATED",
                "GENERATED", "REVIEW", "EXPORTED", "ARCHIVED", "FAILED",
                name="documentstatus",
            ),
            nullable=False,
        ),
        sa.Column("district", sa.String(128), nullable=True, index=True),
        sa.Column("estate", sa.String(128), nullable=True, index=True),
        sa.Column("title", sa.String(512), nullable=True),
        sa.Column("politician", sa.String(256), nullable=True, index=True),
        sa.Column("reference_number", sa.String(128), nullable=True, index=True),
        sa.Column("document_date", sa.DateTime, nullable=True),
        sa.Column("language", sa.String(32), nullable=True),
        sa.Column("version", sa.String(32), nullable=True),
        sa.Column("source", sa.String(64), nullable=True),
        sa.Column("ocr_text", sa.Text, nullable=True),
        sa.Column("keywords", sa.JSON, nullable=True),
        sa.Column("ai_confidence", sa.Float, nullable=True),
        sa.Column("ocr_confidence", sa.Float, nullable=True),
        sa.Column("extracted_fields", sa.JSON, nullable=True),
        sa.Column("output_path", sa.String(1024), nullable=True),
        sa.Column("archive_path", sa.String(1024), nullable=True),
        sa.Column("created_at", sa.DateTime, nullable=False),
        sa.Column("updated_at", sa.DateTime, nullable=False),
    )

    op.create_table(
        "processing_events",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("document_id", sa.String(36), sa.ForeignKey("documents.id"), index=True),
        sa.Column("stage", sa.String(128), nullable=False),
        sa.Column("status", sa.String(64), nullable=False),
        sa.Column("detail", sa.Text, nullable=True),
        sa.Column("duration_ms", sa.Integer, nullable=True),
        sa.Column("created_at", sa.DateTime, nullable=False),
    )

    op.create_table(
        "workflow_runs",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("workflow_name", sa.String(128), nullable=False, index=True),
        sa.Column("status", sa.String(64), nullable=False),
        sa.Column("total_documents", sa.Integer, nullable=False),
        sa.Column("succeeded", sa.Integer, nullable=False),
        sa.Column("failed", sa.Integer, nullable=False),
        sa.Column("started_at", sa.DateTime, nullable=False),
        sa.Column("finished_at", sa.DateTime, nullable=True),
        sa.Column("triggered_by", sa.String(128), nullable=True),
    )

    op.create_table(
        "users",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("username", sa.String(128), nullable=False, unique=True, index=True),
        sa.Column("full_name", sa.String(256), nullable=True),
        sa.Column("hashed_password", sa.String(256), nullable=False),
        sa.Column(
            "role",
            sa.Enum("ADMIN", "EDITOR", "REVIEWER", "VIEWER", name="userrole"),
            nullable=False,
        ),
        sa.Column("is_active", sa.Boolean, nullable=False),
        sa.Column("created_at", sa.DateTime, nullable=False),
    )

    op.create_table(
        "audit_logs",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("actor", sa.String(128), nullable=True),
        sa.Column("action", sa.String(256), nullable=False),
        sa.Column("resource_type", sa.String(128), nullable=True),
        sa.Column("resource_id", sa.String(128), nullable=True),
        sa.Column("detail", sa.JSON, nullable=True),
        sa.Column("success", sa.Boolean, nullable=False),
        sa.Column("created_at", sa.DateTime, nullable=False, index=True),
    )


def downgrade() -> None:
    op.drop_table("audit_logs")
    op.drop_table("users")
    op.drop_table("workflow_runs")
    op.drop_table("processing_events")
    op.drop_table("documents")
