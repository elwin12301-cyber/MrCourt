"""Demo data for a client (default "abc1"): a case with a hearing five days from today, so the reminder texts can be seen.

Development only. Safe to run again (it keeps one demo case; its hearing is moved to five days from today only if it is on another day).

    DATABASE_URL=sqlite:///./dev.db python scripts/seed_abc1.py
    DATABASE_URL=sqlite:///./dev.db python scripts/seed_abc1.py --username abc2 --name "Demo Client" --phone 9876543210

A client that does not exist yet is created (password: the development password). The phone number is marked verified:
only give a number that belongs to someone who agreed to get these texts.
"""

import argparse
from datetime import datetime, timedelta, timezone

from sqlalchemy import select

from mrcourt.db.base import get_sessionmaker, utcnow
from mrcourt.models import Case, CaseInvitation, Hearing, Party, User, UserSettings
from mrcourt.services.session import hash_password
from mrcourt.seed import DEV_PASSWORD
from mrcourt.services.cases import aware
from mrcourt.services.notify import to_msisdn
from mrcourt.services.reminders import IST, forget_reminders

TITLE = "Demo: abc1 v. Sample Traders"
DAYS_AHEAD = 5


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--username", default="abc1")
    parser.add_argument("--name", default="Demo Client")
    parser.add_argument("--phone", default=None, help="needed when the client does not exist yet")
    args = parser.parse_args()
    db = get_sessionmaker()()
    try:
        username = args.username.lower()
        client = db.scalars(select(User).where(User.username == username)).first()
        advocate = db.scalars(select(User).where(User.username == "rohan")).first()
        if advocate is None:
            raise SystemExit("Run the normal seed first so the advocate 'rohan' exists.")
        if client is None:
            mobile = to_msisdn(args.phone or "")
            if mobile is None:
                raise SystemExit("Give --phone for a client that does not exist yet.")
            client = User(
                role="petitioner",
                full_name=args.name,
                username=username,
                email=f"{username}@example.com",
                phone=f"+{mobile}",
                password_hash=hash_password(DEV_PASSWORD),
            )
            client.settings = UserSettings()
            db.add(client)
            db.flush()

        # Marked verified for this demo (the number's owner agreed to get the texts).
        if client.phone_verified_at is None:
            client.phone_verified_at = utcnow()
        if client.settings is not None:
            client.settings.whatsapp_reminders = True  # the "text message reminders" switch

        case = db.scalars(select(Case).where(Case.owner_id == advocate.id, Case.title == TITLE)).first()
        if case is None:
            case = Case(
                owner_id=advocate.id,
                title=TITLE,
                cnr_number="DLCT01-000511-2026",
                court="Saket District Court",
                status="active",
                stage="Evidence",
            )
            case.parties += [
                Party(side="petitioner", name=client.full_name, is_client=True),
                Party(side="respondent", name="Sample Traders Pvt. Ltd."),
            ]
            db.add(case)
            db.flush()
        if not db.scalars(
            select(CaseInvitation).where(CaseInvitation.case_id == case.id, CaseInvitation.invitee_user_id == client.id)
        ).first():
            db.add(
                CaseInvitation(
                    case_id=case.id,
                    invitee_user_id=client.id,
                    status="accepted",
                    invited_by=advocate.id,
                    accepted_at=utcnow(),
                )
            )

        day = datetime.now(IST).date() + timedelta(days=DAYS_AHEAD)
        when = datetime(day.year, day.month, day.day, 10, 30, tzinfo=IST).astimezone(timezone.utc)
        hearing = case.hearings[0] if case.hearings else None
        if hearing is None:
            hearing = Hearing(scheduled_at=when, court_room="Court Room 12")
            case.hearings.append(hearing)
        elif aware(hearing.scheduled_at).astimezone(IST).date() != day:
            hearing.scheduled_at = when
            db.flush()
            forget_reminders(db, hearing)  # the reminder schedule starts again for the new date
        db.commit()
        print(f"{TITLE}: hearing on {day:%d %b %Y} at 10:30 AM IST, client {client.username} ({client.phone}).")
    finally:
        db.close()


if __name__ == "__main__":
    main()
