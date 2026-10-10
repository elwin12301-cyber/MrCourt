"""Admin console: session epoch on users and the audit log.

Revision ID: 0003
Revises: 0002

Like revision 0002, each step checks first, because revision 0001 builds the schema from the current
models: a database created fresh from this code already has these objects.
"""
import sqlalchemy as sa
from alembic import op

import mrcourt.models  # noqa: F401
from mrcourt.db.base import Base

revision = "0003"
down_revision = "0002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    if "session_epoch" not in {c["name"] for c in inspector.get_columns("users")}:
        with op.batch_alter_table("users") as batch:
            batch.add_column(sa.Column("session_epoch", sa.Integer(), nullable=False, server_default="0"))

    if "audit_log" not in set(inspector.get_table_names()):
        Base.metadata.tables["audit_log"].create(bind)


def downgrade() -> None:
    bind = op.get_bind()
    Base.metadata.tables["audit_log"].drop(bind, checkfirst=True)
    inspector = sa.inspect(bind)
    if "session_epoch" in {c["name"] for c in inspector.get_columns("users")}:
        with op.batch_alter_table("users") as batch:
            batch.drop_column("session_epoch")
