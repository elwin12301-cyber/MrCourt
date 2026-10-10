"""First start on a server: create the first administrator.

Run after `alembic upgrade head`: `python -m mrcourt.bootstrap`. Safe to run on every start.
The administrator comes from ADMIN_EMAIL and ADMIN_PASSWORD (set them as secrets on the host);
nothing is created when they are empty or an administrator already exists. No demo accounts are made.
Legal texts are not loaded here: the administrator adds verified documents in the Knowledge base.
"""

import os

from sqlalchemy import select

from mrcourt.db.base import get_sessionmaker
from mrcourt.models import User, UserSettings
from mrcourt.services.session import hash_password


def main() -> None:
    session = get_sessionmaker()()
    try:
        email = os.environ.get("ADMIN_EMAIL", "").strip().lower()
        password = os.environ.get("ADMIN_PASSWORD", "")
        has_admin = session.scalars(select(User).where(User.is_admin.is_(True))).first() is not None
        if email and password and not has_admin:
            if len(password) < 12:
                raise SystemExit("ADMIN_PASSWORD must be at least 12 characters.")
            admin = User(
                role="admin",
                full_name="Administrator",
                email=email,
                username="siteadmin",
                is_admin=True,
                verification_status="verified",
                password_hash=hash_password(password),
            )
            admin.settings = UserSettings()
            session.add(admin)
            print("Created the administrator account.")
        session.commit()
    finally:
        session.close()


if __name__ == "__main__":
    main()
