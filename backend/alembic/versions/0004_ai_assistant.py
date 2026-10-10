"""AI assistant: knowledge documents, private passages, history fields, proposed actions.

Revision ID: 0004
Revises: 0003

Like the earlier revisions, each step checks first, because revision 0001 builds the schema from
the current models: a database created fresh from this code already has these objects. Existing
passages are given a shared, ready document each, and existing citations keep a label snapshot so
they still read correctly if a passage is removed later.
"""
import uuid
from datetime import UTC, datetime

import sqlalchemy as sa
from alembic import op

import mrcourt.models  # noqa: F401
from mrcourt.db.base import Base

revision = "0004"
down_revision = "0003"
branch_labels = None
depends_on = None

NEW_TABLES = ("knowledge_documents", "proposed_actions")

NEW_COLUMNS = [
    ("legal_sources", sa.Column("document_id", sa.Uuid(), nullable=True)),
    ("legal_sources", sa.Column("owner_id", sa.Uuid(), nullable=True)),
    ("legal_sources", sa.Column("page", sa.Integer(), nullable=True)),
    ("questions", sa.Column("input_method", sa.String(10), nullable=False, server_default="typed")),
    ("questions", sa.Column("mode", sa.String(10), nullable=False, server_default="answer")),
    ("answers", sa.Column("answer_mode", sa.String(10), nullable=False, server_default="passages")),
    ("answers", sa.Column("steps", sa.JSON(), nullable=True)),
    ("answer_citations", sa.Column("label", sa.String(400), nullable=True)),
    ("answer_citations", sa.Column("source_url", sa.String(500), nullable=True)),
]


def _columns(inspector: sa.Inspector, table: str) -> dict[str, dict]:
    return {c["name"]: c for c in inspector.get_columns(table)}


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    existing = set(inspector.get_table_names())
    for name in NEW_TABLES:
        if name not in existing:
            Base.metadata.tables[name].create(bind)

    for table, column in NEW_COLUMNS:
        if column.name not in _columns(inspector, table):
            with op.batch_alter_table(table) as batch:
                batch.add_column(column.copy())

    inspector = sa.inspect(bind)
    if not _columns(inspector, "answer_citations")["source_id"]["nullable"]:
        with op.batch_alter_table("answer_citations") as batch:
            batch.alter_column("source_id", existing_type=sa.Uuid(), nullable=True)

    # Backfill: one shared, ready document per passage that has none, and label snapshots.
    now = datetime.now(UTC)
    sources = bind.execute(
        sa.text("SELECT id, kind, citation_label FROM legal_sources WHERE document_id IS NULL")
    ).all()
    docs = Base.metadata.tables["knowledge_documents"]
    for source_id, kind, label in sources:
        doc_id = uuid.uuid4()
        bind.execute(
            docs.insert().values(
                id=doc_id,
                title=label[:300],
                citation=label,
                kind=kind if kind in ("act_section", "judgment", "note") else "act_section",
                owner_id=None,
                status="ready",
                passage_count=1,
                created_at=now,
                updated_at=now,
            )
        )
        bind.execute(
            sa.text("UPDATE legal_sources SET document_id = :d WHERE id = :s"),
            {"d": doc_id.hex if bind.dialect.name == "sqlite" else doc_id, "s": source_id},
        )
    bind.execute(
        sa.text(
            "UPDATE answer_citations SET label = (SELECT citation_label FROM legal_sources "
            "WHERE legal_sources.id = answer_citations.source_id) WHERE label IS NULL"
        )
    )


def downgrade() -> None:
    bind = op.get_bind()
    for table, column in reversed(NEW_COLUMNS):
        inspector = sa.inspect(bind)
        if column.name in _columns(inspector, table):
            with op.batch_alter_table(table) as batch:
                batch.drop_column(column.name)
    for name in reversed(NEW_TABLES):
        Base.metadata.tables[name].drop(bind, checkfirst=True)
