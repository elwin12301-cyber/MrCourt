"""Phone verification, code purposes and the reminder log.

Revision ID: 0006
Revises: 0005

Idempotent like the earlier revisions: a database built fresh from the current models already has
these objects.
"""
import sqlalchemy as sa
from alembic import op

import mrcourt.models  # noqa: F401
from mrcourt.db.base import Base

revision = "0006"
down_revision = "0005"
branch_labels = None
depends_on = None

NEW_COLUMNS = [
    ("users", sa.Column("phone_verified_at", sa.DateTime(timezone=True), nullable=True)),
    ("otp_challenges", sa.Column("purpose", sa.String(20), nullable=False, server_default="login")),
]


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if "reminder_log" not in set(inspector.get_table_names()):
        Base.metadata.tables["reminder_log"].create(bind)
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
    Base.metadata.tables["reminder_log"].drop(bind, checkfirst=True)
