"""WhatsApp channel (feature 010): links, consents, delivery records, incoming messages, conversation state,
and how a question was asked.

Revision ID: 0010
Revises: 0009

Idempotent like the earlier revisions.
"""
import sqlalchemy as sa
from alembic import op

revision = "0010"
down_revision = "0009"
branch_labels = None
depends_on = None

TABLES = ("conversation_state", "inbound_messages", "messages", "message_consents", "whatsapp_links")


def _tables() -> set[str]:
    return set(sa.inspect(op.get_bind()).get_table_names())


def _indexes(table: str) -> set[str]:
    return {i["name"] for i in sa.inspect(op.get_bind()).get_indexes(table)}


def upgrade() -> None:
    have = _tables()
    if "whatsapp_links" not in have:
        op.create_table(
            "whatsapp_links",
            sa.Column("user_id", sa.Uuid(), sa.ForeignKey("users.id", ondelete="CASCADE"), primary_key=True),
            sa.Column("msisdn", sa.String(32), nullable=False),
            sa.Column("linked_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("last_inbound_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("last_sent_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("unlinked_at", sa.DateTime(timezone=True), nullable=True),
        )
        op.create_index("ix_whatsapp_links_msisdn", "whatsapp_links", ["msisdn"], unique=True)
    if "message_consents" not in have:
        op.create_table(
            "message_consents",
            sa.Column("user_id", sa.Uuid(), sa.ForeignKey("users.id", ondelete="CASCADE"), primary_key=True),
            sa.Column("kind", sa.String(20), primary_key=True),
            sa.Column("enabled", sa.Boolean(), nullable=False, server_default=sa.false()),
            sa.Column("changed_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("changed_by", sa.String(12), nullable=False, server_default="person"),
        )
    if "messages" not in have:
        op.create_table(
            "messages",
            sa.Column("id", sa.Uuid(), primary_key=True),
            sa.Column("user_id", sa.Uuid(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
            sa.Column("kind", sa.String(20), nullable=False),
            sa.Column("channel", sa.String(10), nullable=False),
            sa.Column("status", sa.String(10), nullable=False, server_default="queued"),
            sa.Column("provider", sa.String(12), nullable=False, server_default=""),
            sa.Column("provider_message_id", sa.String(255), nullable=True),
            sa.Column("case_id", sa.Uuid(), sa.ForeignKey("cases.id", ondelete="SET NULL"), nullable=True),
            sa.Column("hearing_id", sa.Uuid(), sa.ForeignKey("hearings.id", ondelete="SET NULL"), nullable=True),
            sa.Column("fallback_of", sa.Uuid(), sa.ForeignKey("messages.id", ondelete="SET NULL"), nullable=True),
            sa.Column("failure_reason", sa.String(60), nullable=True),
            sa.Column("send_after", sa.DateTime(timezone=True), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        )
        op.create_index("ix_messages_user_id", "messages", ["user_id"])
        op.create_index("ix_messages_provider_message_id", "messages", ["provider_message_id"])
        op.create_index("ix_messages_created_at", "messages", ["created_at"])
        op.create_index("ix_messages_status_send_after", "messages", ["status", "send_after"])
    if "inbound_messages" not in have:
        op.create_table(
            "inbound_messages",
            sa.Column("id", sa.Uuid(), primary_key=True),
            sa.Column("provider", sa.String(12), nullable=False),
            sa.Column("provider_message_id", sa.String(255), nullable=False),
            sa.Column("user_id", sa.Uuid(), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
            sa.Column("sender_hash", sa.String(64), nullable=False),
            sa.Column("kind", sa.String(16), nullable=False, server_default="text"),
            sa.Column("status", sa.String(10), nullable=False, server_default="received"),
            sa.Column("attempts", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("question_id", sa.Uuid(), sa.ForeignKey("questions.id", ondelete="SET NULL"), nullable=True),
            sa.Column("payload", sa.JSON(), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.UniqueConstraint("provider", "provider_message_id", name="uq_inbound_provider_message"),
        )
        op.create_index("ix_inbound_messages_sender_hash", "inbound_messages", ["sender_hash"])
        op.create_index("ix_inbound_messages_created_at", "inbound_messages", ["created_at"])
    if "conversation_state" not in have:
        op.create_table(
            "conversation_state",
            sa.Column("user_id", sa.Uuid(), sa.ForeignKey("users.id", ondelete="CASCADE"), primary_key=True),
            sa.Column("awaiting", sa.String(20), nullable=False),
            sa.Column("options", sa.JSON(), nullable=False),
            sa.Column("intent", sa.String(12), nullable=False, server_default=""),
            sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        )
    columns = {c["name"] for c in sa.inspect(op.get_bind()).get_columns("questions")}
    if "channel" not in columns:
        with op.batch_alter_table("questions") as batch:
            batch.add_column(sa.Column("channel", sa.String(10), nullable=False, server_default="app"))


def downgrade() -> None:
    columns = {c["name"] for c in sa.inspect(op.get_bind()).get_columns("questions")}
    if "channel" in columns:
        with op.batch_alter_table("questions") as batch:
            batch.drop_column("channel")
    have = _tables()
    for table in TABLES:
        if table in have:
            op.drop_table(table)
