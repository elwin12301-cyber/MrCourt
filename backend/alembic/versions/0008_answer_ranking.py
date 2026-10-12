"""Answers keep a short explanation of how their sources were ranked (feature 009).

Revision ID: 0008
Revises: 0007

Idempotent like the earlier revisions.
"""
import sqlalchemy as sa
from alembic import op

revision = "0008"
down_revision = "0007"
branch_labels = None
depends_on = None


def upgrade() -> None:
    inspector = sa.inspect(op.get_bind())
    if "ranking" not in {c["name"] for c in inspector.get_columns("answers")}:
        with op.batch_alter_table("answers") as batch:
            batch.add_column(sa.Column("ranking", sa.JSON(), nullable=True))


def downgrade() -> None:
    inspector = sa.inspect(op.get_bind())
    if "ranking" in {c["name"] for c in inspector.get_columns("answers")}:
        with op.batch_alter_table("answers") as batch:
            batch.drop_column("ranking")
