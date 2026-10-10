"""Client case status: client-facing status, sharing flags, timeline, updates and questions.

Revision ID: 0002
Revises: 0001

Every step first checks whether the column or table already exists. Revision 0001 builds the
schema from the current models, so a database created fresh from this code already has these
objects, while a database created before this feature does not. The check makes both work.
"""
import sqlalchemy as sa
from alembic import op

import mrcourt.models  # noqa: F401
from mrcourt.db.base import Base

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None

NEW_TABLES = ("timeline_entries", "client_updates", "client_questions")

# (table, column) pairs added to existing tables
NEW_COLUMNS = [
    ("cases", sa.Column("client_status", sa.String(20), nullable=True)),
    ("cases", sa.Column("client_status_changed_at", sa.DateTime(timezone=True), nullable=True)),
    ("cases", sa.Column("client_status_changed_by", sa.Uuid(), sa.ForeignKey("users.id", name="fk_cases_client_status_changed_by"), nullable=True)),
    ("documents", sa.Column("shared_with_client", sa.Boolean(), nullable=False, server_default=sa.false())),
    ("hearings", sa.Column("outcome_shared", sa.Boolean(), nullable=False, server_default=sa.false())),
    ("case_invitations", sa.Column("accepted_at", sa.DateTime(timezone=True), nullable=True)),
    ("user_settings", sa.Column("client_contact", sa.JSON(), nullable=True)),
]


def _columns(inspector: sa.Inspector, table: str) -> set[str]:
    return {c["name"] for c in inspector.get_columns(table)}


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    for table, column in NEW_COLUMNS:
        if column.name not in _columns(inspector, table):
            with op.batch_alter_table(table) as batch:
                batch.add_column(column.copy())

    existing = set(inspector.get_table_names())
    for name in NEW_TABLES:
        if name not in existing:
            Base.metadata.tables[name].create(bind)

    # Invitations accepted before this feature: use the last change time as the acceptance time.
    op.execute(
        "UPDATE case_invitations SET accepted_at = updated_at "
        "WHERE status = 'accepted' AND accepted_at IS NULL"
    )


def downgrade() -> None:
    bind = op.get_bind()
    for name in reversed(NEW_TABLES):
        Base.metadata.tables[name].drop(bind, checkfirst=True)
    inspector = sa.inspect(bind)
    for table, column in reversed(NEW_COLUMNS):
        if column.name in _columns(inspector, table):
            with op.batch_alter_table(table) as batch:
                batch.drop_column(column.name)
