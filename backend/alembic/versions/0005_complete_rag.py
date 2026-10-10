"""Complete RAG: embedding and OCR fields, Text Assistant conversations.

Revision ID: 0005
Revises: 0004

Idempotent like the earlier revisions: a database built fresh from the current models already has
these objects.
"""
import sqlalchemy as sa
from alembic import op

import mrcourt.models  # noqa: F401
from mrcourt.db.base import Base

revision = "0005"
down_revision = "0004"
branch_labels = None
depends_on = None

NEW_TABLES = ("text_conversations", "text_lines")

NEW_COLUMNS = [
    ("legal_sources", sa.Column("embedding_model", sa.String(60), nullable=True)),
    ("legal_sources", sa.Column("read_by_ocr", sa.Boolean(), nullable=False, server_default=sa.false())),
    ("legal_sources", sa.Column("ocr_confidence", sa.Float(), nullable=True)),
    ("knowledge_documents", sa.Column("ocr_pages", sa.Integer(), nullable=False, server_default="0")),
    ("questions", sa.Column("conversation_id", sa.Uuid(), nullable=True)),
]


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    existing = set(inspector.get_table_names())
    for name in NEW_TABLES:
        if name not in existing:
            Base.metadata.tables[name].create(bind)
    for table, column in NEW_COLUMNS:
        if column.name not in {c["name"] for c in inspector.get_columns(table)}:
            with op.batch_alter_table(table) as batch:
                batch.add_column(column.copy())


def downgrade() -> None:
    bind = op.get_bind()
    for table, column in reversed(NEW_COLUMNS):
        inspector = sa.inspect(bind)
        if column.name in {c["name"] for c in inspector.get_columns(table)}:
            with op.batch_alter_table(table) as batch:
                batch.drop_column(column.name)
    for name in reversed(NEW_TABLES):
        Base.metadata.tables[name].drop(bind, checkfirst=True)
