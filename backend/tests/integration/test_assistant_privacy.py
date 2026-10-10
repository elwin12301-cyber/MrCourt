import json

import pytest
from helpers import ScriptedModel, sign_in

from mrcourt.config import get_settings
from mrcourt.services import assistant
from mrcourt.services.assistant import ModelReply, ToolCall

API = "/api/v1/assistant/requests"
SECRET = "ZZ-private-marker-1234"


def call(name, **args):
    return ModelReply(tool_calls=[ToolCall(f"t-{name}", name, args)])


def final(text="Done."):
    return ModelReply(text=json.dumps({"paragraphs": [{"kind": "case", "text": text}]}))


@pytest.fixture(autouse=True)
def _reset(monkeypatch):
    monkeypatch.setattr(get_settings(), "anthropic_api_key", "")
    yield
    assistant.set_model(None)


def _tool_output(model, index=1):
    return json.dumps(model.calls[index]["messages"][-1]["content"])


def _client_case(client):
    return client.get("/api/v1/client/dashboard").json()["cases"][0]


def test_a_clients_assistant_never_sees_private_notes_internal_documents_or_contact_details(client, second_client):
    sign_in(client, "anita.sharma@example.com")
    case = _client_case(client)
    sign_in(second_client, "rohan.sharma@example.com")
    cid = case["id"]
    second_client.patch(f"/api/v1/cases/{cid}", json={"notes": f"Private notes {SECRET}"})
    second_client.post(f"/api/v1/cases/{cid}/timeline", json={"text": f"Private timeline {SECRET}"})
    second_client.post(
        f"/api/v1/cases/{cid}/documents",
        files={"file": (f"internal-{SECRET}.pdf", b"%PDF-1.4 internal", "application/pdf")},
    )

    for name, args in (("get_my_case", {"case_id": cid}), ("list_my_cases", {}), ("list_my_hearings", {})):
        model = ScriptedModel([call(name, **args), final()])
        assistant.set_model(model)
        assert client.post(API, json={"text": "Tell me about my case"}).status_code == 200
        output = _tool_output(model)
        assert SECRET not in output, name
        assert "@example.com" not in output and "phone" not in output.lower(), name


def test_a_client_cannot_read_a_case_that_is_not_theirs(client, second_client):
    sign_in(client, "anita.sharma@example.com")
    sign_in(second_client, "rohan.sharma@example.com")
    created = second_client.post(
        "/api/v1/cases",
        json={
            "title": "Mehta v. Somebody",
            "cnr_number": "TST-0001",
            "court": "Saket District Court",
            "parties": [{"side": "petitioner", "name": "Ravi Mehta", "is_client": True}],
        },
    ).json()
    mine = {c["id"] for c in client.get("/api/v1/client/dashboard").json()["cases"]}
    assert created["id"] not in mine

    model = ScriptedModel([call("get_my_case", case_id=created["id"]), final()])
    assistant.set_model(model)
    body = client.post(API, json={"text": "Show me that case"}).json()
    assert body["steps"][0]["status"] == "refused"
    assert "Not found" in _tool_output(model)
    assert "Mehta" not in _tool_output(model)


def test_an_advocates_assistant_cannot_read_another_advocates_case(client, second_client):
    sign_in(client, "rohan.sharma@example.com")
    case_id = client.get("/api/v1/cases").json()[0]["id"]
    second_client.post(
        "/api/v1/auth/register",
        json={"role": "advocate", "full_name": "Adv. Other", "email": "other@example.com", "password": "a-strong-password"},
    )
    for name, args in (("get_case", {"case_id": case_id}), ("propose_draft", {"template": "notice", "case_id": case_id})):
        model = ScriptedModel([call(name, **args), final()])
        assistant.set_model(model)
        body = second_client.post(API, json={"text": "Use that case"}).json()
        assert body["steps"][0]["status"] == "refused", name
        assert body["proposed_action"] is None, name


def test_hearing_lists_cover_only_the_signed_in_advocates_cases(client, second_client):
    sign_in(client, "rohan.sharma@example.com")
    second_client.post(
        "/api/v1/auth/register",
        json={"role": "advocate", "full_name": "Adv. Other", "email": "other@example.com", "password": "a-strong-password"},
    )
    model = ScriptedModel([call("list_hearings", from_date="2000-01-01", to_date="2100-01-01"), final()])
    assistant.set_model(model)
    assert second_client.post(API, json={"text": "All my hearings"}).status_code == 200
    assert json.loads(model.calls[1]["messages"][-1]["content"][0]["content"].split(": ", 1)[1]) == []

    mine = ScriptedModel([call("list_hearings", from_date="2000-01-01", to_date="2100-01-01"), final()])
    assistant.set_model(mine)
    client.post(API, json={"text": "All my hearings"})
    assert json.loads(mine.calls[1]["messages"][-1]["content"][0]["content"].split(": ", 1)[1])
