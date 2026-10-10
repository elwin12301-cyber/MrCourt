"""Contract tests for dashboard, cases, hearings, documents and invitations."""

import io
from datetime import timedelta

from mrcourt.db.base import utcnow

API = "/api/v1"


def first_case(client):
    return next(c for c in client.get(f"{API}/cases").json() if c["title"] == "Sharma v. Verma Traders")


def test_cases_require_sign_in(client):
    assert client.get(f"{API}/cases").status_code == 401
    assert client.get(f"{API}/dashboard").status_code == 401


def test_list_shape_and_order(advocate_client):
    cases = advocate_client.get(f"{API}/cases").json()
    assert len(cases) == 5
    assert set(cases[0]) == {"id", "title", "cnr_number", "court", "status", "next_hearing_at"}
    dates = [c["next_hearing_at"] for c in cases if c["next_hearing_at"]]
    assert dates == sorted(dates), "cases are ordered by next hearing"
    assert cases[-1]["status"] == "closed" and cases[-1]["next_hearing_at"] is None


def test_search_by_party_cnr_and_court(advocate_client):
    def titles(**params):
        return {c["title"] for c in advocate_client.get(f"{API}/cases", params=params).json()}

    assert titles(q="verma") == {"Sharma v. Verma Traders"}  # title and respondent
    assert titles(q="Anita") == {"Sharma v. Verma Traders"}  # party name only
    assert titles(q="DLHC01-001873") == {"State v. Imran Khan"}
    assert titles(q="patiala") == {"Gupta v. Gupta Estate"}
    assert titles(q="no such thing") == set()


def test_status_filters(advocate_client):
    def titles(status):
        return {c["title"] for c in advocate_client.get(f"{API}/cases", params={"status": status}).json()}

    assert titles("closed") == {"Gupta v. Gupta Estate"}
    assert "Gupta v. Gupta Estate" not in titles("active")
    soon = titles("hearing_soon")
    assert soon and "Mehta Constructions v. NHAI" not in soon  # 21 days away
    assert advocate_client.get(f"{API}/cases", params={"status": "bogus"}).status_code == 422


def test_case_detail_shape(advocate_client):
    case = first_case(advocate_client)
    detail = advocate_client.get(f"{API}/cases/{case['id']}").json()
    assert detail["stage"] == "Evidence"
    assert {p["side"] for p in detail["parties"]} == {"petitioner", "respondent"}
    assert [d["file_name"] for d in detail["documents"]] == [
        "Dishonour memo.pdf", "Legal notice.pdf", "Cheque copy.pdf",
    ]
    assert detail["notes"] is not None


def test_create_edit_and_close_a_case(advocate_client):
    created = advocate_client.post(
        f"{API}/cases",
        json={
            "title": "Nair v. Pillai",
            "cnr_number": "DLCT01-000001-2026",
            "court": "Saket District Court",
            "parties": [{"side": "petitioner", "name": "Nair", "is_client": True}],
        },
    )
    assert created.status_code == 201
    case_id = created.json()["id"]
    edited = advocate_client.patch(f"{API}/cases/{case_id}", json={"stage": "Arguments"})
    assert edited.status_code == 200 and edited.json()["stage"] == "Arguments"
    closed = advocate_client.patch(f"{API}/cases/{case_id}", json={"status": "closed"})
    assert closed.json()["status"] == "closed"


def test_duplicate_cnr_conflicts(advocate_client):
    case = first_case(advocate_client)
    response = advocate_client.post(
        f"{API}/cases",
        json={"title": "Dup", "cnr_number": case["cnr_number"], "court": "X"},
    )
    assert response.status_code == 409


def test_add_and_reschedule_a_hearing(advocate_client):
    case = first_case(advocate_client)
    before = len(advocate_client.get(f"{API}/cases/{case['id']}/hearings").json())
    when = (utcnow() + timedelta(days=40)).replace(microsecond=0).isoformat()
    created = advocate_client.post(
        f"{API}/cases/{case['id']}/hearings", json={"scheduled_at": when, "purpose": "Arguments"}
    )
    assert created.status_code == 201
    hearing_id = created.json()["id"]
    later = (utcnow() + timedelta(days=50)).replace(microsecond=0).isoformat()
    moved = advocate_client.patch(
        f"{API}/cases/{case['id']}/hearings/{hearing_id}", json={"scheduled_at": later}
    )
    assert moved.status_code == 200
    listed = advocate_client.get(f"{API}/cases/{case['id']}/hearings").json()
    assert len(listed) == before + 1


def test_upload_and_list_a_document(advocate_client):
    case = first_case(advocate_client)
    response = advocate_client.post(
        f"{API}/cases/{case['id']}/documents",
        files={"file": ("affidavit.pdf", io.BytesIO(b"%PDF-1.4 test"), "application/pdf")},
    )
    assert response.status_code == 201
    names = [d["file_name"] for d in advocate_client.get(f"{API}/cases/{case['id']}/documents").json()]
    assert "affidavit.pdf" in names


def test_upload_rejects_unsupported_types(advocate_client):
    case = first_case(advocate_client)
    response = advocate_client.post(
        f"{API}/cases/{case['id']}/documents",
        files={"file": ("run.exe", io.BytesIO(b"MZ"), "application/x-msdownload")},
    )
    assert response.status_code == 415


def test_dashboard_shape(advocate_client):
    body = advocate_client.get(f"{API}/dashboard").json()
    assert body["active_cases"] == 4
    assert body["hearings_this_week"] == 3
    assert len(body["upcoming_hearings"]) == 3
    assert [c["title"] for c in body["upcoming_hearings"]][0] == "Sharma v. Verma Traders"
    assert body["recent_activity"][0]["message"] == "Notice served in Sharma v. Verma Traders"
    assert set(body) >= {"drafts_to_review"}
