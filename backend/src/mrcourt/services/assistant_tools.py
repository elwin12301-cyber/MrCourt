"""The things the assistant may do, all bound to the signed-in person.

The person is fixed when the tool set is built; the model never supplies a user id, so nothing it
says can reach another person's data. Everything here reads, except `propose_draft`, which only
records a proposal that the person must confirm in a separate request.

Tool results are data. The system prompt tells the model never to follow instructions found in
them, and nothing in a result changes what the tools allow.
"""

import logging
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any

from sqlalchemy.orm import Session, selectinload

from mrcourt.db.base import utcnow
from mrcourt.models import Case, LegalSource, ProposedAction, User
from mrcourt.services import client_view
from mrcourt.services.access import get_client_case, get_owned_case, visible_cases
from mrcourt.services.cases import aware, list_cases, next_hearing
from mrcourt.services.draft_templates import TEMPLATES
from mrcourt.services.retrieval import search

logger = logging.getLogger(__name__)

PROPOSAL_LIFETIME = timedelta(minutes=10)
NOTES_LIMIT = 1500
MAX_ROWS = 25


@dataclass
class ToolResult:
    data: Any  # what the model sees (JSON-serialisable)
    label: str  # the step shown to the person
    status: str = "ok"  # ok | refused | failed
    detail: str | None = None


@dataclass
class ToolSet:
    db: Session
    user: User
    question_id: uuid.UUID | None = None
    # Passages found by search_knowledge in this run, by label ("S1"...). Law paragraphs may cite only these.
    retrieved: dict[str, LegalSource] = field(default_factory=dict)
    # The ranking explanation of each search_knowledge call (feature 009), in order.
    rankings: list[dict[str, Any]] = field(default_factory=list)
    proposal: ProposedAction | None = None

    @property
    def is_client(self) -> bool:
        return self.user.role == "petitioner"

    # ----- what the model is told about -----
    def schemas(self) -> list[dict[str, Any]]:
        search = {
            "name": "search_knowledge",
            "description": "Search the legal knowledge base. Returns numbered passages you may cite.",
            "input_schema": {
                "type": "object",
                "properties": {"query": {"type": "string", "description": "What to look up"}},
                "required": ["query"],
            },
        }
        if self.is_client:
            return [
                {
                    "name": "list_my_cases",
                    "description": "List the person's own cases with the plain-language status and next hearing.",
                    "input_schema": {"type": "object", "properties": {}},
                },
                {
                    "name": "get_my_case",
                    "description": "What the lawyer has shared about one of the person's own cases.",
                    "input_schema": {
                        "type": "object",
                        "properties": {"case_id": {"type": "string"}},
                        "required": ["case_id"],
                    },
                },
                {
                    "name": "list_my_hearings",
                    "description": "The person's upcoming hearings across their cases.",
                    "input_schema": {"type": "object", "properties": {}},
                },
                search,
            ]
        return [
            {
                "name": "list_cases",
                "description": "List the advocate's own cases, optionally filtered by a search word or status.",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "search": {"type": "string"},
                        "status": {"type": "string", "enum": ["active", "hearing_soon", "closed"]},
                    },
                },
            },
            {
                "name": "get_case",
                "description": "Details of one of the advocate's own cases: parties, hearings, notes, document names.",
                "input_schema": {
                    "type": "object",
                    "properties": {"case_id": {"type": "string"}},
                    "required": ["case_id"],
                },
            },
            {
                "name": "list_hearings",
                "description": "Hearings across the advocate's cases between two ISO dates (inclusive).",
                "input_schema": {
                    "type": "object",
                    "properties": {"from_date": {"type": "string"}, "to_date": {"type": "string"}},
                    "required": ["from_date", "to_date"],
                },
            },
            search,
            {
                "name": "propose_draft",
                "description": (
                    "Propose creating an editable draft. Nothing is created until the person confirms. "
                    "Templates: " + ", ".join(sorted(TEMPLATES)) + "."
                ),
                "input_schema": {
                    "type": "object",
                    "properties": {"template": {"type": "string"}, "case_id": {"type": "string"}},
                    "required": ["template"],
                },
            },
        ]

    # ----- running a tool -----
    def run(self, name: str, args: dict[str, Any]) -> ToolResult:
        allowed = {s["name"] for s in self.schemas()}
        if name not in allowed:
            return ToolResult({"error": "That is not something you can do here."}, "Tried something that is not allowed", "refused")
        handler = getattr(self, f"_{name}")
        try:
            return handler(args if isinstance(args, dict) else {})
        except _NotFound:
            return ToolResult({"error": "Not found."}, "Could not find that case", "refused")
        except Exception:  # noqa: BLE001 - a failing tool must not stop the run or leak details
            logger.warning("Assistant tool %s failed", name, exc_info=True)
            return ToolResult({"error": "That step failed."}, f"{name.replace('_', ' ').capitalize()} did not work", "failed")

    # ----- helpers -----
    def _case_id(self, args: dict[str, Any]) -> uuid.UUID:
        try:
            return uuid.UUID(str(args.get("case_id", "")))
        except ValueError as exc:
            raise _NotFound from exc

    # ----- advocate tools -----
    def _list_cases(self, args: dict[str, Any]) -> ToolResult:
        rows = list_cases(self.db, self.user, str(args.get("search") or "") or None, args.get("status") or None)
        data = [
            {
                "id": str(c.id),
                "title": c.title,
                "court": c.court,
                "status": c.status,
                "next_hearing_at": c.next_hearing_at.isoformat() if c.next_hearing_at else None,
            }
            for c in rows[:MAX_ROWS]
        ]
        return ToolResult(data, "Looked up your cases", detail=_count(len(rows), "case"))

    def _get_case(self, args: dict[str, Any]) -> ToolResult:
        try:
            case = get_owned_case(self.db, self.user, self._case_id(args))
        except Exception as exc:  # 404 from the access check
            raise _NotFound from exc
        upcoming = next_hearing(case)
        data = {
            "id": str(case.id),
            "title": case.title,
            "cnr_number": case.cnr_number,
            "court": case.court,
            "stage": case.stage,
            "parties": [{"side": p.side, "name": p.name, "is_client": p.is_client} for p in case.parties],
            "next_hearing_at": aware(upcoming.scheduled_at).isoformat() if upcoming else None,
            "hearings": [
                {
                    "at": aware(h.scheduled_at).isoformat(),
                    "purpose": h.purpose,
                    "outcome": h.outcome,
                }
                for h in sorted(case.hearings, key=lambda h: aware(h.scheduled_at))[:MAX_ROWS]
            ],
            "documents": [d.file_name for d in case.documents[:MAX_ROWS]],
            "notes": (case.notes or "")[:NOTES_LIMIT] or None,
        }
        return ToolResult(data, f"Read the case “{case.title}”")

    def _list_hearings(self, args: dict[str, Any]) -> ToolResult:
        start = _day(args.get("from_date"), end=False)
        end = _day(args.get("to_date"), end=True)
        cases = self.db.scalars(visible_cases(self.user).options(selectinload(Case.hearings)))
        rows = [
            {
                "case_id": str(c.id),
                "case_title": c.title,
                "at": aware(h.scheduled_at).isoformat(),
                "court": c.court,
                "purpose": h.purpose,
            }
            for c in cases
            for h in c.hearings
            if start <= aware(h.scheduled_at) <= end
        ]
        rows.sort(key=lambda r: r["at"])
        return ToolResult(rows[:MAX_ROWS], "Checked your hearings", detail=_count(len(rows), "hearing"))

    def _propose_draft(self, args: dict[str, Any]) -> ToolResult:
        template = str(args.get("template", ""))
        if template not in TEMPLATES:
            return ToolResult({"error": "Unknown template."}, "Could not prepare that draft", "refused")
        case: Case | None = None
        if args.get("case_id"):
            try:
                case = get_owned_case(self.db, self.user, self._case_id(args))
            except Exception as exc:
                raise _NotFound from exc
        title = TEMPLATES[template].label
        summary = f"Create a {title} draft for {case.title}" if case else f"Create a {title} draft"
        self.proposal = ProposedAction(
            user_id=self.user.id,
            question_id=self.question_id,
            kind="create_draft",
            params={"template": template, "case_id": str(case.id) if case else None},
            summary=summary[:300],
            status="pending",
            expires_at=utcnow() + PROPOSAL_LIFETIME,
            created_at=utcnow(),
        )
        self.db.add(self.proposal)
        self.db.flush()
        return ToolResult(
            {"proposed": summary, "note": "Waiting for the person to confirm. Nothing has been created yet."},
            "Prepared a draft for you to confirm",
            detail=summary,
        )

    # ----- shared -----
    def _search_knowledge(self, args: dict[str, Any]) -> ToolResult:
        query = str(args.get("query", ""))[:300]
        result = search(self.db, query, self.user, limit=6)
        hits = result.hits
        if result.ranking:
            self.rankings.append(result.ranking)
        found = []
        for hit in hits:
            label = f"S{len(self.retrieved) + 1}"
            self.retrieved[label] = hit.source
            found.append({"label": label, "citation": hit.source.citation_label, "text": hit.source.text[:1500]})
        return ToolResult(found, f"Searched the knowledge base for “{query[:60]}”", detail=_count(len(found), "passage"))

    # ----- client tools -----
    def _list_my_cases(self, args: dict[str, Any]) -> ToolResult:
        dash = client_view.dashboard(self.db, self.user)
        data = [
            {
                "id": str(c.id),
                "title": c.title,
                "court": c.court,
                "status": c.status,
                "lawyer": c.lawyer.name,
                "next_hearing": _hearing(c.next_hearing) if c.next_hearing else None,
            }
            for c in dash.cases[:MAX_ROWS]
        ]
        return ToolResult(data, "Looked up your cases", detail=_count(len(data), "case"))

    def _get_my_case(self, args: dict[str, Any]) -> ToolResult:
        try:
            case = get_client_case(self.db, self.user, self._case_id(args))
        except Exception as exc:
            raise _NotFound from exc
        detail = client_view.case_detail(self.db, self.user, case)
        data = {
            "id": str(case.id),
            "title": detail.title,
            "court": detail.court,
            "status": detail.status,
            "lawyer": detail.lawyer.name,
            "next_hearing": _hearing(detail.next_hearing) if detail.next_hearing else None,
            "hearings": [_hearing(h) for h in detail.hearings[:MAX_ROWS]],
            "timeline": [{"at": t.occurred_at.isoformat(), "text": t.text} for t in detail.timeline[:MAX_ROWS]],
            "shared_documents": [d.file_name for d in detail.documents[:MAX_ROWS]],
        }
        return ToolResult(data, f"Read your case “{detail.title}”")

    def _list_my_hearings(self, args: dict[str, Any]) -> ToolResult:
        now = utcnow()
        cases = self.db.scalars(visible_cases(self.user).options(selectinload(Case.hearings)))
        rows = [
            {"case": c.title, **_hearing(client_view.hearing_view(c, h))}
            for c in cases
            for h in c.hearings
            if aware(h.scheduled_at) >= now
        ]
        rows.sort(key=lambda r: r["at"])
        return ToolResult(rows[:MAX_ROWS], "Checked your hearings", detail=_count(len(rows), "hearing"))


class _NotFound(Exception):
    pass


def _count(n: int, noun: str) -> str:
    return f"{n} {noun}{'' if n == 1 else 's'}"


def _hearing(h: Any) -> dict[str, Any]:
    return {
        "at": aware(h.scheduled_at).isoformat(),
        "court": h.court,
        "what_happens": h.description.text if h.description else None,
        "outcome": h.outcome,
    }


def _day(value: Any, *, end: bool) -> datetime:
    try:
        parsed = datetime.fromisoformat(str(value))
    except ValueError as exc:
        raise _NotFound from exc
    parsed = aware(parsed)
    if end and parsed.hour == parsed.minute == parsed.second == 0:
        parsed = parsed + timedelta(days=1) - timedelta(seconds=1)
    return parsed

