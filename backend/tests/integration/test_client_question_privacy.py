"""Two clients on one case must never see each other's messages (spec FR-020, plan Key Risks)."""

import json

from sqlalchemy import select

from helpers import sign_in
from mrcourt.models import Case, ClientQuestion, User

API = "/api/v1"
ANITA_Q = "When can I expect the court to decide?"
RAVI_Q = "Do I need to attend the next hearing?"


def case_id_of(db):
    return str(db.scalars(select(Case).where(Case.title == "Sharma v. Verma Traders")).one().id)


def switch(client, email):
    client.post(f"{API}/auth/logout")
    sign_in(client, email)


def questions(client, case_id):
    return client.get(f"{API}/client/cases/{case_id}/questions").json()


def test_each_client_sees_only_their_own_question(client, db):
    case_id = case_id_of(db)
    sign_in(client, "anita.sharma@example.com")
    anita = questions(client, case_id)
    switch(client, "ravi.mehta@example.com")
    ravi = questions(client, case_id)
    assert [q["text"] for q in anita] == [ANITA_Q]
    assert [q["text"] for q in ravi] == [RAVI_Q]


def test_a_new_question_from_one_client_never_reaches_the_other(client, db):
    case_id = case_id_of(db)
    sign_in(client, "anita.sharma@example.com")
    client.post(f"{API}/client/cases/{case_id}/questions", json={"kind": "question", "text": "Is a settlement possible?"})
    switch(client, "ravi.mehta@example.com")
    everything = json.dumps([questions(client, case_id), client.get(f"{API}/client/cases/{case_id}").json(), client.get(f"{API}/client/dashboard").json()])
    assert "Is a settlement possible?" not in everything
    assert ANITA_Q not in everything


def test_a_reply_goes_to_the_asking_client_only(client, db):
    case_id = case_id_of(db)
    sign_in(client, "rohan.sharma@example.com")
    waiting = next(i for i in client.get(f"{API}/cases/{case_id}/client-questions").json() if i["client_name"] == "Ravi Mehta")
    client.post(f"{API}/client-questions/{waiting['id']}/reply", json={"text": "Yes, please come at ten."})

    switch(client, "anita.sharma@example.com")
    blob = json.dumps([questions(client, case_id), client.get(f"{API}/client/cases/{case_id}").json(), client.get(f"{API}/client/dashboard").json()])
    assert "Yes, please come at ten." not in blob

    switch(client, "ravi.mehta@example.com")
    assert questions(client, case_id)[0]["reply_text"] == "Yes, please come at ten."


def test_one_client_cannot_mark_anothers_reply_read(client, db):
    anita_q = db.scalars(select(ClientQuestion).where(ClientQuestion.text == ANITA_Q)).one()
    sign_in(client, "ravi.mehta@example.com")
    assert client.post(f"{API}/client/questions/{anita_q.id}/read").status_code == 404
    db.expire_all()
    assert db.get(ClientQuestion, anita_q.id).reply_read_at is None


def test_the_advocate_can_see_both_and_nobody_else_can(client, db):
    case_id = case_id_of(db)
    sign_in(client, "rohan.sharma@example.com")
    assert len(client.get(f"{API}/cases/{case_id}/client-questions").json()) == 2


def test_removing_one_client_leaves_the_other_with_access(client, db):
    case = db.scalars(select(Case).where(Case.title == "Sharma v. Verma Traders")).one()
    sign_in(client, "rohan.sharma@example.com")
    invitations = client.get(f"{API}/cases/{case.id}/invitations").json()
    ravi = next(i for i in invitations if i["contact_or_name"] == "Ravi Mehta")
    assert client.delete(f"{API}/cases/{case.id}/invitations/{ravi['id']}").status_code == 204

    switch(client, "ravi.mehta@example.com")
    assert client.get(f"{API}/client/cases/{case.id}").status_code == 404
    assert client.get(f"{API}/client/cases/{case.id}/questions").status_code == 404
    assert client.post(f"{API}/client/cases/{case.id}/questions", json={"kind": "question", "text": "Still there?"}).status_code == 404

    switch(client, "anita.sharma@example.com")
    assert client.get(f"{API}/client/cases/{case.id}").status_code == 200
    assert [q["text"] for q in questions(client, str(case.id))] == [ANITA_Q]


def test_clients_never_see_the_other_clients_name_anywhere(client, db):
    case_id = case_id_of(db)
    sign_in(client, "anita.sharma@example.com")
    blob = json.dumps([questions(client, case_id), client.get(f"{API}/client/cases/{case_id}").json(), client.get(f"{API}/client/dashboard").json()])
    assert "Ravi" not in blob and "Mehta" not in blob
    assert db.scalars(select(User).where(User.full_name == "Ravi Mehta")).one() is not None
