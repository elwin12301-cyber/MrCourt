"""Document details (feature 008): mapped metadata on knowledge documents, the Acts and sections they refer to,
and the section numbers each statute passage carries.

Revision ID: 0009
Revises: 0008

Idempotent like the earlier revisions.
"""
import sqlalchemy as sa
from alembic import op

revision = "0009"
down_revision = "0008"
branch_labels = None
depends_on = None

DOC_COLUMNS = [
    sa.Column("details", sa.JSON(), nullable=True),
    sa.Column("doc_type", sa.String(20), nullable=True),
    sa.Column("court", sa.String(200), nullable=True),
    sa.Column("case_number", sa.String(60), nullable=True),
    sa.Column("decided_on", sa.Date(), nullable=True),
    sa.Column("language", sa.String(10), nullable=True),
    sa.Column("text_quality", sa.String(12), nullable=True),
]
SOURCE_COLUMNS = [
    sa.Column("sections", sa.JSON(), nullable=True),
    sa.Column("chapter", sa.String(100), nullable=True),
]
INDEXED = ("doc_type", "court", "case_number")


def _columns(table: str) -> set[str]:
    return {c["name"] for c in sa.inspect(op.get_bind()).get_columns(table)}


def upgrade() -> None:
    have = _columns("knowledge_documents")
    with op.batch_alter_table("knowledge_documents") as batch:
        for column in DOC_COLUMNS:
            if column.name not in have:
                batch.add_column(column.copy())
    indexes = {i["name"] for i in sa.inspect(op.get_bind()).get_indexes("knowledge_documents")}
    for name in INDEXED:
        if f"ix_knowledge_documents_{name}" not in indexes:
            op.create_index(f"ix_knowledge_documents_{name}", "knowledge_documents", [name])

    have = _columns("legal_sources")
    with op.batch_alter_table("legal_sources") as batch:
        for column in SOURCE_COLUMNS:
            if column.name not in have:
                batch.add_column(column.copy())

    if "document_references" not in sa.inspect(op.get_bind()).get_table_names():
        op.create_table(
            "document_references",
            sa.Column("id", sa.Uuid(), primary_key=True),
            sa.Column("document_id", sa.Uuid(), sa.ForeignKey("knowledge_documents.id", ondelete="CASCADE"), nullable=False),
            sa.Column("act", sa.String(30), nullable=False),
            sa.Column("section", sa.String(20), nullable=True),
            sa.UniqueConstraint("document_id", "act", "section", name="uq_document_reference"),
        )
        op.create_index("ix_document_references_document_id", "document_references", ["document_id"])
        op.create_index("ix_document_references_act_section", "document_references", ["act", "section"])


def downgrade() -> None:
    if "document_references" in sa.inspect(op.get_bind()).get_table_names():
        op.drop_table("document_references")
    have = _columns("legal_sources")
    with op.batch_alter_table("legal_sources") as batch:
        for column in SOURCE_COLUMNS:
            if column.name in have:
                batch.drop_column(column.name)
    indexes = {i["name"] for i in sa.inspect(op.get_bind()).get_indexes("knowledge_documents")}
    for name in INDEXED:
        if f"ix_knowledge_documents_{name}" in indexes:
            op.drop_index(f"ix_knowledge_documents_{name}", table_name="knowledge_documents")
    have = _columns("knowledge_documents")
    with op.batch_alter_table("knowledge_documents") as batch:
        for column in DOC_COLUMNS:
            if column.name in have:
                batch.drop_column(column.name)
