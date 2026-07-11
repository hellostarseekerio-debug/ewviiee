"""multi-factor authentication support

Revision ID: 0003
Revises: 0002
Create Date: 2026-07-11

"""
from alembic import op
import sqlalchemy as sa

revision = "0003"
down_revision = "0002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "users", sa.Column("mfa_enabled", sa.Boolean, nullable=False, server_default=sa.false())
    )
    op.add_column("users", sa.Column("mfa_secret_encrypted", sa.String(512), nullable=True))
    op.add_column("users", sa.Column("mfa_pending_secret_encrypted", sa.String(512), nullable=True))
    op.add_column("users", sa.Column("mfa_recovery_codes", sa.JSON, nullable=True))


def downgrade() -> None:
    op.drop_column("users", "mfa_recovery_codes")
    op.drop_column("users", "mfa_pending_secret_encrypted")
    op.drop_column("users", "mfa_secret_encrypted")
    op.drop_column("users", "mfa_enabled")
