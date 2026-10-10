"""Initial schema

Revision ID: 0001
Revises:
"""
from alembic import op

import mrcourt.models  # noqa: F401
from mrcourt.db.base import Base

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        op.execute("CREATE EXTENSION IF NOT EXISTS vector")
    Base.metadata.create_all(bind)
    if bind.dialect.name == "postgresql":
        # Full-text search over legal passages (queried with the same expression).
        op.execute(
            "CREATE INDEX IF NOT EXISTS ix_legal_sources_fts "
            "ON legal_sources USING GIN (to_tsvector('english', "
            "coalesce(citation_label,'') || ' ' || text))"
        )
        op.execute(
            "CREATE INDEX IF NOT EXISTS ix_legal_sources_embedding "
            "ON legal_sources USING hnsw (embedding vector_cosine_ops)"
        )
        op.execute("CREATE INDEX IF NOT EXISTS ix_hearings_scheduled ON hearings (scheduled_at)")
        op.execute("CREATE INDEX IF NOT EXISTS ix_cases_owner ON cases (owner_id)")


def downgrade() -> None:
    bind = op.get_bind()
    Base.metadata.drop_all(bind)
