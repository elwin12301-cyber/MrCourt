"""The four draft templates. Facts we do not hold stay as [bracketed placeholders], never invented."""

from dataclasses import dataclass
from typing import Callable


@dataclass
class DraftContext:
    case_title: str | None = None
    cnr_number: str | None = None
    court: str | None = None
    client: str | None = None
    respondent: str | None = None


@dataclass
class Rendered:
    title: str
    body: str


@dataclass
class Template:
    key: str
    label: str
    subtitle: str  # short line under the title, as in the prototype
    render: Callable[[DraftContext], Rendered]


def _or(value: str | None, placeholder: str) -> str:
    return value if value else placeholder


def _case_line(c: DraftContext) -> str:
    if not c.case_title:
        return ""
    cnr = f" (CNR {c.cnr_number})" if c.cnr_number else ""
    return f"\n\nIn the matter of: {c.case_title}{cnr}."


def _notice(c: DraftContext) -> Rendered:
    client = _or(c.client, "[client name]")
    other = _or(c.respondent, "[name of the drawer]")
    return Rendered(
        title=f"Legal Notice — {_or(c.respondent, _or(c.case_title, '[Case]'))}",
        body=(
            "Subject: Notice under Section 138 of the Negotiable Instruments Act, 1881.\n\n"
            f"Under instructions from and on behalf of my client, {client}, I hereby call upon "
            f"you, {other}, to pay ₹[amount] against Cheque No. [cheque number] dated [date], "
            "which was dishonoured on presentation with the remark “[reason given by the bank]”, "
            "within 15 days of receipt of this notice, failing which my client shall be "
            "constrained to initiate criminal proceedings against you."
            f"{_case_line(c)}"
        ),
    )


def _bail(c: DraftContext) -> Rendered:
    court = _or(c.court, "[court]").upper()
    return Rendered(
        title=f"Bail Application — {_or(c.case_title, '[Case]')}",
        body=(
            f"IN THE {court}\n\n"
            "Application for regular bail under Section 483 of the Bharatiya Nagarik Suraksha "
            f"Sanhita, 2023.{_case_line(c)}\n\n"
            "1. Brief facts of the case\n"
            "2. Grounds for grant of bail\n"
            "3. Applicant’s ties to the community and willingness to comply with conditions\n"
            "4. Prayer"
        ),
    )


def _reply(c: DraftContext) -> Rendered:
    client = _or(c.client, "[client name]")
    return Rendered(
        title=f"Reply to Notice — {_or(c.case_title, '[Case]')}",
        body=(
            "Sir/Madam,\n\n"
            f"Under instructions from my client, {client}, I respond to your notice dated [date] "
            "as follows:\n\n"
            "1. The contents of paragraphs 1 to [n] are denied as incorrect.\n"
            "2. [Client’s version of facts]\n"
            "3. My client reserves all rights and remedies available in law."
            f"{_case_line(c)}"
        ),
    )


def _affidavit(c: DraftContext) -> Rendered:
    deponent = _or(c.client, "[deponent name]")
    return Rendered(
        title=f"Affidavit — {_or(c.client, _or(c.case_title, '[Case]'))}",
        body=(
            "AFFIDAVIT\n\n"
            f"I, {deponent}, aged [age] years, resident of [address], do hereby solemnly affirm "
            "and state on oath as follows:\n\n"
            "1. That I am the petitioner in the above matter and am competent to swear this "
            "affidavit.\n"
            "2. That the contents of the accompanying petition are true to my knowledge."
            f"{_case_line(c)}\n\n"
            "DEPONENT"
        ),
    )


TEMPLATES: dict[str, Template] = {
    t.key: t
    for t in (
        Template("notice", "Legal Notice", "Section 138 NI Act", _notice),
        Template("bail", "Bail Application", "Outline", _bail),
        Template("reply", "Reply to Notice", "Skeleton", _reply),
        Template("affidavit", "Affidavit", "Skeleton", _affidavit),
    )
}
