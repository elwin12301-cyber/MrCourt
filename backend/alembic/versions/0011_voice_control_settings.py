"""Voice control (feature 011): consent time, the cloud option and the language, kept with the person's settings.

Revision ID: 0011
Revises: 0010

Idempotent like the earlier revisions. Nothing about what was said is stored.
"""
import sqlalchemy as sa
from alembic import op

revision = "0011"
down_revision = "0010"
branch_labels = None
depends_on = None


def _columns() -> set[str]:
    return {c["name"] for c in sa.inspect(op.get_bind()).get_columns("user_settings")}


def upgrade() -> None:
    have = _columns()
    if "voice_consent_at" not in have:
        op.add_column("user_settings", sa.Column("voice_consent_at", sa.DateTime(timezone=True), nullable=True))
    if "voice_cloud_opt_in" not in have:
        op.add_column("user_settings", sa.Column("voice_cloud_opt_in", sa.Boolean(), nullable=False, server_default=sa.false()))
    if "voice_language" not in have:
        op.add_column("user_settings", sa.Column("voice_language", sa.String(8), nullable=True))


def downgrade() -> None:
    have = _columns()
    for name in ("voice_language", "voice_cloud_opt_in", "voice_consent_at"):
        if name in have:
            op.drop_column("user_settings", name)
