"""poster archive: real status lifecycle

Revision ID: 0006
Revises: 0005
Create Date: 2026-07-13

Adds `posters.status` (draft/pending_review/approved/published/rejected/
archived - see PosterStatus in app/core/models.py and the transition rules
in app/posters/status.py), replacing the flat, un-actionable "Pending"
every poster was previously stuck at.

`approval_status` is deliberately kept, not dropped - it's backfilled to
stay consistent with the new `status` column (see
app.posters.status.approval_status_for) for one deprecation cycle so
anything still reading the old field alone keeps working.
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0006"
down_revision = "0005"
branch_labels = None
depends_on = None

# See 0002/0005's matching comment: on Postgres an enum is its own schema
# object that op.add_column() only references, never creates - so it must
# be created explicitly here. SQLite has no native enum type and ignores
# this (Enum degrades to a VARCHAR + CHECK constraint there).
poster_status_enum = postgresql.ENUM(
    "DRAFT", "PENDING_REVIEW", "APPROVED", "PUBLISHED", "REJECTED", "ARCHIVED",
    name="posterstatus", create_type=False,
)


def upgrade() -> None:
    poster_status_enum.create(op.get_bind(), checkfirst=True)

    op.add_column(
        "posters",
        sa.Column("status", poster_status_enum, nullable=False, server_default="PENDING_REVIEW"),
    )
    op.create_index("ix_posters_status", "posters", ["status"])

    # Backfill existing rows from their current approval_status so nothing
    # that was already approved/rejected silently reverts to "pending
    # review" - the server_default above only covers newly inserted rows.
    op.execute(
        """
        UPDATE posters
        SET status = CASE approval_status
            WHEN 'APPROVED' THEN 'APPROVED'
            WHEN 'REJECTED' THEN 'REJECTED'
            ELSE 'PENDING_REVIEW'
        END
        """
    )


def downgrade() -> None:
    op.drop_index("ix_posters_status", table_name="posters")
    op.drop_column("posters", "status")
    poster_status_enum.drop(op.get_bind(), checkfirst=True)
