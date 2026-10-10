"""Contract tests for questions from clients to their advocate."""

import uuid

import pytest
from sqlalchemy import select

from helpers import sign_in
from mrcourt.models import Case, ClientQuestion, User

API = "/api/v1"
ADVOCATE = "rohan.sharma@example.com"
ANITA = "anita.sharma@example.com"
RAVI = "ravi.mehta@example.com"


def switch(client, email):
    client.post(f"{API}/auth/logout")
    sign_in(client, email)


def case_id_of(db):
    return str(db.scalars(select(Case).where(Case.title == "Sharma v. Verma Traders")).one().id)


def test_a_client_lists_only_their_own_questions(petitioner_client, db):
    items = petitioner_client.get(f"{API}/client/cases/{case_id_of(db)}/questions").json()
    assert len(items) == 1
    q = items[0]
    assert set(q) == {"id", "kind", "text", "sent_at", "reply_text", "replied_at", "reply_read"}
    assert q["text"] == "When can I expect the court to decide?"
    assert q["reply_text"].startswith("After evidence and arguments")
    assert q["reply_read"] is False


def test_a_question_waiting_for_a_reply_shows_no_reply(client, db):
    sign_in(client, RAVI)
    q = client.get(f"{API}/client/cases/{case_id_of(db)}/questions").json()[0]
    assert q["reply_text"] is None and q["replied_at"] is None


def test_send_a_question(petitioner_client, db):
    case_id = case_id_of(db)
    response = petitioner_client.post(f"{API}/client/cases/{case_id}/questions", json={"kind": "question", "text": "What should I bring?"})
    assert response.status_code == 201
    body = response.json()
    assert body["kind"] == "question" and body["text"] == "What should I bring?" and body["reply_text"] is None
    texts = [q["text"] for q in petitioner_client.get(f"{API}/client/cases/{case_id}/questions").json()]
    assert "What should I bring?" in texts


def test_ask_for_an_update_needs_no_text(petitioner_client, db):
    response = petitioner_client.post(f"{API}/client/cases/{case_id_of(db)}/questions", json={"kind": "update_request"})
    assert response.status_code == 201
    assert response.json()["kind"] == "update_request" and response.json()["text"]


@pytest.mark.parametrize("text", [None, "", "   ", "x" * 2001])
def test_a_question_needs_real_text_of_sensible_length(petitioner_client, db, text):
    body = {"kind": "question"} if text is None else {"kind": "question", "text": text}
    assert petitioner_client.post(f"{API}/client/cases/{case_id_of(db)}/questions", json=body).status_code == 422


def test_cannot_ask_about_a_case_you_are_not_on(petitioner_client, db):
    other = str(db.scalars(select(Case).where(Case.title == "State v. Imran Khan")).one().id)
    assert petitioner_client.post(f"{API}/client/cases/{other}/questions", json={"kind": "question", "text": "Hi"}).status_code == 404
    assert petitioner_client.get(f"{API}/client/cases/{other}/questions").status_code == 404


def test_messages_are_rate_limited(petitioner_client, db):
    case_id = case_id_of(db)
    codes = [
        petitioner_client.post(f"{API}/client/cases/{case_id}/questions", json={"kind": "question", "text": f"Question {i}"}).status_code
        for i in range(22)
    ]
    assert codes[:20] == [201] * 20 and 429 in codes[20:]


def test_the_client_is_told_when_the_lawyer_is_no_longer_on_mrcourt(petitioner_client, db):
    owner = db.get(User, db.scalars(select(Case).where(Case.title == "Sharma v. Verma Traders")).one().owner_id)
    owner.status = "deactivated"
    db.commit()
    response = petitioner_client.post(f"{API}/client/cases/{case_id_of(db)}/questions", json={"kind": "question", "text": "Hello?"})
    assert response.status_code == 409
    assert "no longer available" in response.json()["detail"].lower()


def test_marking_a_reply_read(petitioner_client, db):
    case_id = case_id_of(db)
    q = petitioner_client.get(f"{API}/client/cases/{case_id}/questions").json()[0]
    assert petitioner_client.post(f"{API}/client/questions/{q['id']}/read").status_code == 204
    assert petitioner_client.get(f"{API}/client/cases/{case_id}/questions").json()[0]["reply_read"] is True


# ---- the advocate's side --------------------------------------------------------------------


def test_the_advocate_sees_every_clients_questions_with_names(advocate_client, db):
    items = advocate_client.get(f"{API}/cases/{case_id_of(db)}/client-questions").json()
    assert {i["client_name"] for i in items} == {"Anita Sharma", "Ravi Mehta"}
    assert all("text" in i and "reply_text" in i for i in items)


def test_the_advocate_replies_once(advocate_client, db):
    items = advocate_client.get(f"{API}/cases/{case_id_of(db)}/client-questions").json()
    waiting = next(i for i in items if i["client_name"] == "Ravi Mehta")
    ok = advocate_client.post(f"{API}/client-questions/{waiting['id']}/reply", json={"text": "Yes, please attend."})
    assert ok.status_code == 200 and ok.json()["reply_text"] == "Yes, please attend."
    again = advocate_client.post(f"{API}/client-questions/{waiting['id']}/reply", json={"text": "Changed my mind."})
    assert again.status_code == 409


@pytest.mark.parametrize("text", ["", "   ", "x" * 2001])
def test_a_reply_needs_real_text(advocate_client, db, text):
    waiting = next(i for i in advocate_client.get(f"{API}/cases/{case_id_of(db)}/client-questions").json() if not i["reply_text"])
    assert advocate_client.post(f"{API}/client-questions/{waiting['id']}/reply", json={"text": text}).status_code == 422


def test_clients_cannot_reply_or_read_the_advocates_list(petitioner_client, db):
    q = db.scalars(select(ClientQuestion)).first()
    assert petitioner_client.get(f"{API}/cases/{case_id_of(db)}/client-questions").status_code in (403, 404)
    assert petitioner_client.post(f"{API}/client-questions/{q.id}/reply", json={"text": "x"}).status_code in (403, 404)


def test_another_advocate_cannot_reply(client, db):
    q = db.scalars(select(ClientQuestion)).first()
    client.post(f"{API}/auth/register", json={"role": "advocate", "full_name": "Other", "email": "other-q@example.com", "password": "a-strong-password"})
    assert client.post(f"{API}/client-questions/{q.id}/reply", json={"text": "x"}).status_code == 404
    assert client.get(f"{API}/cases/{case_id_of(db)}/client-questions").status_code == 404
    assert client.post(f"{API}/client-questions/{uuid.uuid4()}/reply", json={"text": "x"}).status_code == 404
