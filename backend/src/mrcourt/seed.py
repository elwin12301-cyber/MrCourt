"""Seed fictional development data. Refuses to run in production."""

from datetime import timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from mrcourt.config import get_settings
from mrcourt.db.base import get_sessionmaker, utcnow
from mrcourt.models import (
    ActivityEvent,
    Case,
    CaseInvitation,
    ClientQuestion,
    ClientUpdate,
    Document,
    Draft,
    Hearing,
    Party,
    TimelineEntry,
    User,
    UserSettings,
)
from mrcourt.services.draft_templates import TEMPLATES
from mrcourt.services.drafting import context_for
from mrcourt.services.session import hash_password

DEV_PASSWORD = "password123"  # fictional development credential only


def _user(db: Session, **fields: object) -> User:
    existing = db.scalars(select(User).where(User.email == fields["email"])).first()
    if existing:
        return existing
    password = fields.pop("password", DEV_PASSWORD)
    user = User(password_hash=hash_password(str(password)), **fields)
    user.settings = UserSettings()
    db.add(user)
    db.flush()
    return user


def seed(db: Session) -> None:
    now = utcnow()
    advocate = _user(
        db,
        role="advocate",
        full_name="Adv. Rohan Sharma",
        email="rohan.sharma@example.com",
        username="rohan",
        bar_registration_number="D/1234/2015",
        verification_status="verified",
    )
    petitioner = _user(
        db, role="petitioner", full_name="Anita Sharma", email="anita.sharma@example.com", username="anita"
    )
    _user(
        db,
        role="admin",
        full_name="Site Administrator",
        email="admin@example.com",
        username="siteadmin",
        is_admin=True,
        verification_status="verified",
    )

    if db.scalars(select(Case).where(Case.owner_id == advocate.id)).first():
        return

    specs = [
        ("Sharma v. Verma Traders", "DLCT01-004512-2026", "Saket District Court", "active", 2, "10:30"),
        ("State v. Imran Khan", "DLHC01-001873-2025", "Delhi High Court", "active", 5, "14:00"),
        ("Rao v. Rao (Maintenance)", "DLSW02-009341-2026", "Family Court, Dwarka", "active", 6, "11:15"),
        ("Mehta Constructions v. NHAI", "DLHC01-007720-2024", "Delhi High Court", "active", 21, "10:00"),
        ("Gupta v. Gupta Estate", "DLND01-002206-2023", "Patiala House Courts", "closed", None, ""),
    ]
    cases: list[Case] = []
    for title, cnr, court, status, days, at in specs:
        case = Case(owner_id=advocate.id, title=title, cnr_number=cnr, court=court, status=status)
        if days is not None:
            hour, minute = (int(x) for x in at.split(":"))
            when = (now + timedelta(days=days)).replace(hour=hour, minute=minute, second=0, microsecond=0)
            case.hearings.append(Hearing(scheduled_at=when, court_room="Court Room 12"))
        db.add(case)
        cases.append(case)
    db.flush()

    first = cases[0]
    first.stage = "Evidence"
    first.notes = "Private note: prepare cross-examination of the respondent's witness before the next date."
    first.parties += [
        Party(side="petitioner", name="Anita Sharma", is_client=True),
        Party(side="respondent", name="Verma Traders Pvt. Ltd."),
    ]
    for name, size in (("Dishonour memo.pdf", 1_200_000), ("Legal notice.pdf", 340_000), ("Cheque copy.pdf", 860_000)):
        first.documents.append(
            Document(
                file_name=name,
                size_bytes=size,
                content_type="application/pdf",
                storage_key=f"seed/{name}",
                uploaded_by=advocate.id,
            )
        )
    for case, key in zip(cases[:3], ("notice", "bail", "reply")):
        rendered = TEMPLATES[key].render(context_for(case))
        db.add(
            Draft(
                case_id=case.id,
                author_id=advocate.id,
                template=key,
                title=rendered.title,
                body=rendered.body,
            )
        )
    db.add(CaseInvitation(case_id=first.id, invitee_user_id=petitioner.id, status="accepted", invited_by=advocate.id, accepted_at=now - timedelta(days=5)))
    for kind, message, hours in (
        ("notice_served", "Notice served in Sharma v. Verma Traders", 2),
        ("order_uploaded", "New order uploaded in State v. Imran Khan", 26),
        ("invite_accepted", "Anita Rao accepted your case invite", 27),
    ):
        db.add(ActivityEvent(user_id=advocate.id, kind=kind, message=message, created_at=now - timedelta(hours=hours)))

    _seed_client_data(db, now, advocate, petitioner, cases)


def _seed_client_data(db: Session, now, advocate: User, petitioner: User, cases: list[Case]) -> None:
    """Statuses, sharing choices, a second client, updates and questions for the client view."""
    second = _user(db, role="petitioner", full_name="Ravi Mehta", email="ravi.mehta@example.com", username="ravi")
    first = cases[0]
    db.add(
        CaseInvitation(
            case_id=first.id,
            invitee_user_id=second.id,
            status="accepted",
            invited_by=advocate.id,
            accepted_at=now - timedelta(days=3),
        )
    )

    # What the advocate has told clients about each case.
    for case, status, days in zip(cases, ("hearing_scheduled", "awaiting_order", "notice_stage", "notice_stage", "closed"), (1, 4, 9, 12, 30)):
        case.client_status = status
        case.client_status_changed_at = now - timedelta(days=days)
        case.client_status_changed_by = advocate.id

    # The first case has a purpose for its upcoming hearing and two past hearings.
    upcoming = first.hearings[0]
    upcoming.purpose = "Evidence"
    shared_past = Hearing(case_id=first.id, scheduled_at=now - timedelta(days=10), purpose="Notice and appearance", court_room="Court Room 12", outcome="Respondent appeared and was given time to reply.", outcome_shared=True)
    private_past = Hearing(case_id=first.id, scheduled_at=now - timedelta(days=20), purpose="First hearing", court_room="Court Room 12", outcome="Settlement discussed informally; client undecided.", outcome_shared=False)
    db.add_all([shared_past, private_past])
    db.flush()

    # Documents: one shared with the client, the rest internal.
    for document in first.documents:
        document.shared_with_client = document.file_name == "Legal notice.pdf"

    def entry(kind: str, text: str, when, shared: bool, **links: object) -> TimelineEntry:
        e = TimelineEntry(case_id=first.id, kind=kind, text=text, shared_with_client=shared, occurred_at=when, created_by=advocate.id, **links)
        db.add(e)
        return e

    entry("hearing_scheduled", "Hearing listed for evidence.", now - timedelta(days=2), True, hearing_id=upcoming.id)
    entry("status_change", "Status changed to Hearing scheduled.", now - timedelta(days=1), True)
    entry("outcome", "Hearing on notice and appearance: the respondent appeared and was given time to reply.", now - timedelta(days=10), True, hearing_id=shared_past.id)
    entry("outcome", "Private: settlement discussed informally; client undecided.", now - timedelta(days=20), False, hearing_id=private_past.id)
    entry("note", "Private note: prepare cross-examination of the respondent's witness.", now - timedelta(days=2), False)
    update = entry("update", "Your next hearing is for evidence. Please bring a photo ID.", now - timedelta(hours=5), True)
    db.flush()

    # Notices: one unread and one read for the first client, one unread for the second.
    db.add(ClientUpdate(client_id=petitioner.id, case_id=first.id, timeline_entry_id=update.id, kind="update", message=f"{first.title}: Your next hearing is for evidence. Please bring a photo ID.", created_at=now - timedelta(hours=5)))
    db.add(ClientUpdate(client_id=petitioner.id, case_id=first.id, kind="status_change", message=f"{first.title}: Status changed to Hearing scheduled.", created_at=now - timedelta(days=1), read_at=now - timedelta(hours=20)))
    db.add(ClientUpdate(client_id=second.id, case_id=first.id, timeline_entry_id=update.id, kind="update", message=f"{first.title}: Your next hearing is for evidence. Please bring a photo ID.", created_at=now - timedelta(hours=5)))

    # Questions: one answered (first client), one waiting (second client). Private to each.
    db.add(ClientQuestion(case_id=first.id, client_id=petitioner.id, kind="question", text="When can I expect the court to decide?", reply_text="After evidence and arguments. I will update you when a date is fixed.", replied_at=now - timedelta(hours=30), replied_by=advocate.id, created_at=now - timedelta(days=2)))
    db.add(ClientQuestion(case_id=first.id, client_id=second.id, kind="question", text="Do I need to attend the next hearing?", created_at=now - timedelta(hours=3)))

    # What clients may see about the advocate. Email is left out on purpose.
    advocate.settings.client_contact = {"phone": "+91 98100 12345", "office": "Chamber 14, Saket Courts, New Delhi"}


def main() -> None:
    if get_settings().environment == "production":
        raise SystemExit("Refusing to seed development data in production")
    session = get_sessionmaker()()
    try:
        seed(session)
        session.commit()
        print("Seeded development data.")
    finally:
        session.close()


if __name__ == "__main__":
    main()
