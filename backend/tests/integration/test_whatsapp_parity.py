"""The same question gives the same outcome, answer and citations on WhatsApp and on the website (SC-004)."""
import pytest
from helpers import make_document
from helpers_whatsapp import NUMBER, linked, send
from sqlalchemy import select

from mrcourt.models import LegalSource, Question

QUESTIONS = [
    "What does Section 138 NI Act say about cheque dishonour?",
    "Explain cheque dishonour notice",
    "What is the GST rate on gold jewellery?",
    "What does Section 999 of the NI Act say about cheque dishonour?",
    "Should I accept the settlement in my case about cheque dishonour?",
]


@pytest.fixture
def law(db):
    exact = make_document(db, title="Negotiable Instruments Act, 1881", citation="NI Act s.138", kind="act_section",
                          passages=["Dishonour of cheque for insufficiency of funds in the account."])
    make_document(db, title="Negotiable Instruments notes", citation="NI notes", kind="act_section",
                  passages=["Cheque dishonour: when a cheque is dishonoured the payee may sue; cheque dishonour notice."])
    db.flush()
    db.scalars(select(LegalSource).where(LegalSource.document_id == exact.id)).first().section = "138"
    db.commit()


@pytest.mark.parametrize("who", ["anita.sharma@example.com", "rohan.sharma@example.com"])
def test_a_question_has_the_same_answer_on_both_channels(who, client, db, law, fake_channel, monkeypatch) -> None:
    from helpers import sign_in

    from mrcourt.config import get_settings

    monkeypatch.setattr(get_settings(), "whatsapp_questions_per_minute", 100)  # this test asks several in a row

    linked(db, who)
    sign_in(client, who)
    for number, text in enumerate(QUESTIONS):
        website = client.post("/api/v1/questions", json={"text": text}).json()
        send(client, text=text, id=f"w{number}")
        db.expire_all()
        on_whatsapp = db.scalars(select(Question).where(Question.channel == "whatsapp").order_by(Question.created_at.desc())).first()
        stored = on_whatsapp.answer
        assert stored.outcome == website["outcome"], text
        assert [(p["text"], p["citation_numbers"]) for p in stored.paragraphs] == [
            (p["text"], p["citation_numbers"]) for p in website["paragraphs"]
        ], text
        assert [c.label for c in sorted(stored.citations, key=lambda c: c.position)] == [c["label"] for c in website["citations"]], text
        reply = fake_channel.texts_to(NUMBER)[-1]
        if website["message"]:
            assert website["message"] in reply, text  # for example "Not found in the sources: Section 999 NI..."
        assert website["disclaimer"] in reply
        assert (website["lawyer_reminder"] in reply) if website["lawyer_reminder"] else True
        assert (website["case_specific_notice"] in reply) if website["case_specific_notice"] else True
