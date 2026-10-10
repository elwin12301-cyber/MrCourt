import json
import uuid
from datetime import timedelta

import pytest
from helpers import ScriptedModel, sign_in
from sqlalchemy import select

from mrcourt.config import get_settings
from mrcourt.db.base import utcnow
from mrcourt.models import Draft, ProposedAction
from mrcourt.services import assistant
from mrcourt.services.assistant import ModelReply, ToolCall

API = "/api/v1/assistant"


def call(name, **args):
    return ModelReply(tool_calls=[ToolCall(f"t-{name}", name, args)])


def final(text="I have prepared a draft; it needs your confirmation."):
    return ModelReply(text=json.dumps({"paragraphs": [{"kind": "case", "text": text}]}))


@pytest.fixture(autouse=True)
def _reset(monkeypatch):
    monkeypatch.setattr(get_settings(), "anthropic_api_key", "")
    yield
    assistant.set_model(None)


def _propose(client, template="notice", case_id=None):
    args = {"template": template}
    if case_id:
        args["case_id"] = case_id
    assistant.set_model(ScriptedModel([call("propose_draft", **args), final()]))
    return client.post(f"{API}/requests", json={"text": "Prepare a legal notice"}).json()


def _drafts(db):
    db.expire_all()
    return len(db.scalars(select(Draft)).all())


def test_a_proposal_creates_nothing_until_it_is_confirmed(advocate_client, db):
    before = _drafts(db)
    body = _propose(advocate_client)
    action = body["proposed_action"]
    assert action["kind"] == "create_draft" and "Legal Notice" in action["summary"]
    assert _drafts(db) == before


def test_confirming_creates_one_editable_draft_flagged_for_review(advocate_client, db):
    before = _drafts(db)
    action = _propose(advocate_client)["proposed_action"]
    response = advocate_client.post(f"{API}/actions/{action['id']}/confirm")
    assert response.status_code == 200 and response.json()["status"] == "done"
    assert _drafts(db) == before + 1
    draft = advocate_client.get(f"/api/v1/drafts/{response.json()['draft_id']}").json()
    assert draft["title"] and draft.get("review_flag", True)


def test_a_proposal_for_a_case_names_it_and_the_draft_is_linked(advocate_client, db):
    case = advocate_client.get("/api/v1/cases").json()[0]
    action = _propose(advocate_client, case_id=case["id"])["proposed_action"]
    assert case["title"] in action["summary"]
    draft_id = advocate_client.post(f"{API}/actions/{action['id']}/confirm").json()["draft_id"]
    assert advocate_client.get(f"/api/v1/drafts/{draft_id}").json()["case_id"] == case["id"]


def test_a_proposal_works_only_once(advocate_client, db):
    action = _propose(advocate_client)["proposed_action"]
    assert advocate_client.post(f"{API}/actions/{action['id']}/confirm").status_code == 200
    before = _drafts(db)
    assert advocate_client.post(f"{API}/actions/{action['id']}/confirm").status_code == 404
    assert _drafts(db) == before


def test_declining_changes_nothing_and_cannot_be_undone_by_confirming(advocate_client, db):
    before = _drafts(db)
    action = _propose(advocate_client)["proposed_action"]
    assert advocate_client.post(f"{API}/actions/{action['id']}/decline").json() == {"status": "declined", "draft_id": None}
    assert advocate_client.post(f"{API}/actions/{action['id']}/confirm").status_code == 404
    assert _drafts(db) == before


def test_an_expired_proposal_is_refused_and_creates_nothing(advocate_client, db):
    before = _drafts(db)
    action = _propose(advocate_client)["proposed_action"]
    row = db.get(ProposedAction, uuid.UUID(action["id"]))
    row.expires_at = utcnow() - timedelta(minutes=1)
    db.commit()
    response = advocate_client.post(f"{API}/actions/{action['id']}/confirm")
    assert response.status_code == 410
    assert _drafts(db) == before
    assert advocate_client.post(f"{API}/actions/{action['id']}/confirm").status_code == 410


def test_only_the_person_who_was_asked_can_confirm(client, second_client, db):
    sign_in(client, "rohan.sharma@example.com")
    action = _propose(client)["proposed_action"]
    sign_in(second_client, "anita.sharma@example.com")
    before = _drafts(db)
    assert second_client.post(f"{API}/actions/{action['id']}/confirm").status_code == 404
    assert second_client.post(f"{API}/actions/{action['id']}/decline").status_code == 404
    assert _drafts(db) == before
    assert db.get(ProposedAction, uuid.UUID(action["id"])).status == "pending"


def test_an_unknown_template_is_never_proposed(advocate_client):
    body = _propose(advocate_client, template="nonsense")
    assert body["proposed_action"] is None and body["steps"][0]["status"] == "refused"


def test_a_failed_run_does_not_leave_a_live_proposal(advocate_client, db):
    class Breaks:
        calls = 0

        def __call__(self, **kwargs):
            Breaks.calls += 1
            if Breaks.calls == 1:
                return call("propose_draft", template="notice")
            raise RuntimeError("boom")

    assistant.set_model(Breaks())
    body = advocate_client.post(f"{API}/requests", json={"text": "Prepare a notice"}).json()
    assert body["proposed_action"] is None
    db.expire_all()
    assert all(a.status != "pending" for a in db.scalars(select(ProposedAction)))
