"""housing estate application wizard

Revision ID: 0009
Revises: 0008
Create Date: 2026-07-13

Adds the `applications` table backing the new AI Housing Estate
Application wizard (see app/core/models.py's Application/ApplicationStatus
and app/applications/ for the step-validation and service layer this
table supports). A brand-new table, so this is purely additive - nothing
existing is touched.
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0009"
down_revision = "0008"
branch_labels = None
depends_on = None

# See 0001's matching comment: op.create_table()'s implicit CREATE TYPE
# for this Enum column has no checkfirst, so downgrade() must drop it
# explicitly once the owning table is gone, or a downgrade+re-upgrade
# cycle fails with "type ... already exists". No-op on SQLite.
_application_status_enum = postgresql.ENUM(
    "DRAFT", "EDITING_LETTER", "REPLACING_IMAGES", "GENERATING",
    "QUALITY_CHECK", "READY", "EXPORTED", "FAILED",
    name="applicationstatus",
)


def upgrade() -> None:
    op.create_table(
        "applications",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "status",
            sa.Enum(
                "DRAFT", "EDITING_LETTER", "REPLACING_IMAGES", "GENERATING",
                "QUALITY_CHECK", "READY", "EXPORTED", "FAILED",
                name="applicationstatus",
            ),
            nullable=False,
        ),
        sa.Column("current_step", sa.Integer, nullable=False, server_default="1"),
        sa.Column("poster_id", sa.String(36), sa.ForeignKey("posters.id"), nullable=True),
        sa.Column("application_pdf_path", sa.String(1024), nullable=True),
        sa.Column("generated_pdf_path", sa.String(1024), nullable=True),
        sa.Column("template_used", sa.String(256), nullable=True),
        sa.Column("dropbox_folder_url", sa.String(1024), nullable=True),
        sa.Column("image_links", sa.JSON, nullable=True),
        sa.Column("ai_logs", sa.JSON, nullable=True),
        sa.Column("step_history", sa.JSON, nullable=True),
        sa.Column("quality_check_results", sa.JSON, nullable=True),
        sa.Column("export_package_path", sa.String(1024), nullable=True),
        sa.Column("started_by", sa.String(36), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("completed_by", sa.String(36), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("started_at", sa.DateTime, nullable=False),
        sa.Column("completed_at", sa.DateTime, nullable=True),
        sa.Column("created_at", sa.DateTime, nullable=False),
        sa.Column("updated_at", sa.DateTime, nullable=False),
    )
    op.create_index("ix_applications_status", "applications", ["status"])
    op.create_index("ix_applications_current_step", "applications", ["current_step"])
    op.create_index("ix_applications_poster_id", "applications", ["poster_id"])
    op.create_index("ix_applications_started_at", "applications", ["started_at"])
    op.create_index("ix_applications_created_at", "applications", ["created_at"])


def downgrade() -> None:
    op.drop_index("ix_applications_created_at", table_name="applications")
    op.drop_index("ix_applications_started_at", table_name="applications")
    op.drop_index("ix_applications_poster_id", table_name="applications")
    op.drop_index("ix_applications_current_step", table_name="applications")
    op.drop_index("ix_applications_status", table_name="applications")
    op.drop_table("applications")
    _application_status_enum.drop(op.get_bind(), checkfirst=True)
