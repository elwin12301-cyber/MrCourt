"""Usernames: a unique, optional sign-in name.

Revision ID: 0007
Revises: 0006

Existing accounts get a username made from the start of their email address (letters, digits, dots,
dashes and underscores), made unique with a number when needed. Idempotent like the earlier revisions.
"""
import re
import uuid

import sqlalchemy as sa
from alembic import op

revision = "0007"
down_revision = "0006"
branch_labels = None
depends_on = None


def _candidate(email: str | None, user_id: str) -> str:
    base = re.sub(r"[^a-z0-9._-]", "", (email or "").split("@")[0].lower())
    if not base or not base[0].isalpha():
        base = "user" + base
    base = base[:26]
    return base if len(base) >= 3 else f"user{user_id[:6]}"


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if "username" not in {c["name"] for c in inspector.get_columns("users")}:
        with op.batch_alter_table("users") as batch:
            batch.add_column(sa.Column("username", sa.String(30), nullable=True))
            batch.create_unique_constraint("uq_users_username", ["username"])
    taken = {r[0] for r in bind.execute(sa.text("SELECT username FROM users WHERE username IS NOT NULL"))}
    rows = bind.execute(sa.text("SELECT id, email FROM users WHERE username IS NULL ORDER BY created_at")).all()
    for row_id, email in rows:
        text_id = str(row_id).replace("-", "")
        name = _candidate(email, text_id)
        candidate, number = name, 1
        while candidate in taken:
            number += 1
            candidate = f"{name[: 29 - len(str(number))]}{number}"
        taken.add(candidate)
        bind.execute(sa.text("UPDATE users SET username = :u WHERE id = :i"), {"u": candidate, "i": row_id})


def downgrade() -> None:
    inspector = sa.inspect(op.get_bind())
    if "username" in {c["name"] for c in inspector.get_columns("users")}:
        with op.batch_alter_table("users") as batch:
            batch.drop_constraint("uq_users_username", type_="unique")
            batch.drop_column("username")
