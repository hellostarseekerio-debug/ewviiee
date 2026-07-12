"""poster archive: paste-text Dropbox link management

Revision ID: 0005
Revises: 0004
Create Date: 2026-07-12

Adds the `posters` table backing the new Poster Archive page: staff paste a
block of text containing one or more Dropbox links, app/posters/parser.py
extracts district/estate/title/type/route/date/language/keywords per
record, and each becomes one row here. Independent of the existing
`documents` table on purpose - a poster row is a reference to a Dropbox
folder parsed from unstructured text, not a file this platform has itself
processed.

Reuses the `approvalstatus` enum type created in 0002 (documents.
approval_status) rather than defining a second, differently-named enum for
the same three states - see the postgresql.ENUM(..., create_type=False)
note below for why this must NOT try to (re-)create that type.
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0005"
down_revision = "0004"
branch_labels = None
depends_on = None

# create_type=False: this references the *existing* "approvalstatus" type
# (created once, in 0002, for documents.approval_status) rather than
# creating a second type of the same name - op.create_table()'s automatic
# CREATE TYPE (see 0002's comment on this exact mechanism) would otherwise
# collide with "type already exists" the moment a second table also uses a
# plain inline sa.Enum(..., name="approvalstatus").
approval_status_enum = postgresql.ENUM(
    "PENDING", "APPROVED", "REJECTED", name="approvalstatus", create_type=False
)


def upgrade() -> None:
    op.create_table(
        "posters",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("district", sa.String(128), nullable=True, index=True),
        sa.Column("estate", sa.String(128), nullable=True, index=True),
        sa.Column("poster_title", sa.String(512), nullable=True),
        sa.Column("poster_type", sa.String(128), nullable=True, index=True),
        sa.Column("route_number", sa.String(32), nullable=True, index=True),
        sa.Column("document_date", sa.DateTime, nullable=True, index=True),
        sa.Column("language", sa.String(32), nullable=True),
        sa.Column("keywords", sa.JSON, nullable=True),
        # unique=True enforces "no duplicated Dropbox links" at the database
        # level (the import endpoint also pre-checks this in bulk before
        # inserting, so a large paste never fails outright over one
        # repeated link) and gives it an index to use. Nullable to support
        # the "Missing Dropbox" filter - a standard SQL UNIQUE constraint
        # already treats every NULL as distinct from every other NULL, so
        # multiple link-less rows coexist without conflict.
        sa.Column("dropbox_url", sa.String(1024), nullable=True, unique=True, index=True),
        sa.Column("notes", sa.Text, nullable=True),
        sa.Column("source_text", sa.Text, nullable=True),
        sa.Column("workflow_steps", sa.JSON, nullable=True),
        sa.Column("approval_status", approval_status_enum, nullable=False, server_default="PENDING"),
        sa.Column("ai_summary", sa.Text, nullable=True),
        sa.Column("ocr_text", sa.Text, nullable=True),
        sa.Column("attachments", sa.JSON, nullable=True),
        sa.Column("created_at", sa.DateTime, nullable=False),
        sa.Column("updated_at", sa.DateTime, nullable=False),
    )
    op.create_index("ix_posters_approval_status", "posters", ["approval_status"])


def downgrade() -> None:
    op.drop_index("ix_posters_approval_status", table_name="posters")
    op.drop_table("posters")
    # Do NOT drop the "approvalstatus" type here - 0002's downgrade already
    # owns dropping it (after documents.approval_status is gone), and it is
    # still in use by documents at this point in a downgrade sequence.
