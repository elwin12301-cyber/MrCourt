"""Data access/export and account deactivation (DPDP Act; spec FR-015 and Clarification 5).

Deactivation removes the person's own data (identity, contact details, settings, question
history, sign-in codes, activity feed) and keeps case records, which are retained for legal
record-keeping. The user is told this before confirming (enforced by the API).
"""

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from mrcourt.db.base import utcnow
from mrcourt.models import (
    ActivityEvent,
    Case,
    CaseInvitation,
    ClientQuestion,
    ClientUpdate,
    Draft,
    KnowledgeDocument,
    LegalSource,
    ProposedAction,
    TextConversation,
    TextLine,
    TimelineEntry,
    OtpChallenge,
    Question,
    User,
    UserSettings,
)
from mrcourt.services.cases import aware
from mrcourt.services.knowledge import delete_private_documents


def _iso(value: object) -> str | None:
    return aware(value).isoformat() if value is not None else None  # type: ignore[arg-type]


def export_data(db: Session, user: User) -> dict[str, object]:
    settings = user.settings
    questions = db.scalars(
        select(Question).where(Question.user_id == user.id).order_by(Question.created_at)
    ).all()
    drafts = db.scalars(select(Draft).where(Draft.author_id == user.id)).all()
    cases = db.scalars(select(Case).where(Case.owner_id == user.id)).all()
    events = db.scalars(select(ActivityEvent).where(ActivityEvent.user_id == user.id)).all()
    return {
        "profile": {
            "id": str(user.id),
            "role": user.role,
            "full_name": user.full_name,
            "email": user.email,
            "phone": user.phone,
            "bar_registration_number": user.bar_registration_number,
            "verification_status": user.verification_status,
            "created_at": _iso(user.created_at),
        },
        "settings": {
            "language": settings.language,
            "whatsapp_reminders": settings.whatsapp_reminders,
            "hearing_alert_days": settings.hearing_alert_days,
            "theme": settings.theme,
        }
        if settings
        else None,
        "questions": [
            {
                "asked_at": _iso(q.created_at),
                "text": q.text,
                "outcome": q.answer.outcome if q.answer else None,
                "answer": q.answer.paragraphs if q.answer else None,
                "input_method": q.input_method,
                "mode": q.mode,
                "steps": q.answer.steps if q.answer else None,
            }
            for q in questions
        ],
        "text_conversations": [
            {
                "title": c.title,
                "language": c.language,
                "deleted": c.deleted_at is not None,
                "lines": [{"text": line.text, "source": line.source, "at": _iso(line.created_at)} for line in c.lines],
            }
            for c in db.scalars(select(TextConversation).where(TextConversation.user_id == user.id))
        ],
        "private_documents": [
            {
                "title": d.title,
                "citation": d.citation,
                "text": "\n\n".join(
                    p.text for p in db.scalars(select(LegalSource).where(LegalSource.document_id == d.id).order_by(LegalSource.page))
                ),
            }
            for d in db.scalars(select(KnowledgeDocument).where(KnowledgeDocument.owner_id == user.id))
        ],
        "drafts": [
            {"title": d.title, "template": d.template, "version": d.version, "body": d.body}
            for d in drafts
        ],
        "cases": [
            {
                "title": c.title,
                "cnr_number": c.cnr_number,
                "court": c.court,
                "status": c.status,
                "stage": c.stage,
                "parties": [{"side": p.side, "name": p.name} for p in c.parties],
                "hearings": [_iso(h.scheduled_at) for h in c.hearings],
                "documents": [d.file_name for d in c.documents],
                "client_status": c.client_status,
                "timeline": [
                    {"kind": e.kind, "text": e.text, "shared_with_client": e.shared_with_client, "at": _iso(e.occurred_at)}
                    for e in db.scalars(select(TimelineEntry).where(TimelineEntry.case_id == c.id).order_by(TimelineEntry.occurred_at))
                ],
            }
            for c in cases
        ],
        "activity": [{"message": e.message, "at": _iso(e.created_at)} for e in events],
        # A client's own messages and notices (never anyone else's).
        "client_questions": [
            {
                "sent_at": _iso(q.created_at),
                "text": q.text,
                "reply": q.reply_text,
                "replied_at": _iso(q.replied_at),
            }
            for q in db.scalars(
                select(ClientQuestion).where(ClientQuestion.client_id == user.id).order_by(ClientQuestion.created_at)
            )
        ],
        "client_updates": [
            {"message": u.message, "at": _iso(u.created_at), "read": u.read_at is not None}
            for u in db.scalars(
                select(ClientUpdate).where(ClientUpdate.client_id == user.id).order_by(ClientUpdate.created_at)
            )
        ],
        # What an advocate has chosen to show clients about themselves.
        "client_contact": (settings.client_contact if settings and settings.client_contact else None),
    }


def deactivate(db: Session, user: User) -> None:
    question_ids = select(Question.id).where(Question.user_id == user.id)
    from mrcourt.models import Answer, AnswerCitation  # local import keeps the module header short

    answer_ids = select(Answer.id).where(Answer.question_id.in_(question_ids))
    db.execute(delete(ProposedAction).where(ProposedAction.user_id == user.id))
    conversation_ids = select(TextConversation.id).where(TextConversation.user_id == user.id)
    db.execute(delete(TextLine).where(TextLine.conversation_id.in_(conversation_ids)))
    db.execute(delete(TextConversation).where(TextConversation.user_id == user.id))
    db.execute(delete(AnswerCitation).where(AnswerCitation.answer_id.in_(answer_ids)))
    db.execute(delete(Answer).where(Answer.question_id.in_(question_ids)))
    db.execute(delete(Question).where(Question.user_id == user.id))
    delete_private_documents(db, user)  # the person's own notes and their files go with them
    db.execute(delete(OtpChallenge).where(OtpChallenge.user_id == user.id))
    # A client's own messages and notices go with them; the advocate's case records stay.
    db.execute(delete(ClientQuestion).where(ClientQuestion.client_id == user.id))
    db.execute(delete(ClientUpdate).where(ClientUpdate.client_id == user.id))
    db.execute(delete(ActivityEvent).where(ActivityEvent.user_id == user.id))
    db.execute(delete(UserSettings).where(UserSettings.user_id == user.id))
    for invitation in db.scalars(
        select(CaseInvitation).where(CaseInvitation.invitee_user_id == user.id)
    ):
        invitation.status = "removed"

    user.full_name = "Deactivated user"
    user.email = None
    user.phone = None
    user.password_hash = None
    user.bar_registration_number = None
    user.verification_status = "none"
    user.status = "deactivated"
    user.deactivated_at = utcnow()
    db.flush()
