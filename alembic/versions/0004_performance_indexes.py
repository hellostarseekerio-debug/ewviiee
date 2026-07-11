"""performance indexes for search/listing at scale

Revision ID: 0004
Revises: 0003
Create Date: 2026-07-11

"""
from alembic import op

revision = "0004"
down_revision = "0003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Every document listing/search query orders by created_at DESC and
    # frequently filters by document_date range - both were unindexed,
    # forcing a full-table scan/sort once the documents table grows into
    # the thousands of rows a busy office will accumulate.
    op.create_index("ix_documents_created_at", "documents", ["created_at"])
    op.create_index("ix_documents_document_date", "documents", ["document_date"])


def downgrade() -> None:
    op.drop_index("ix_documents_document_date", table_name="documents")
    op.drop_index("ix_documents_created_at", table_name="documents")
