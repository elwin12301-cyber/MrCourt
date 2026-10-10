import uuid
from types import SimpleNamespace

from mrcourt.services.citations import GeneratedParagraph, verify


def source(section: str | None, text: str = "text", label: str | None = None):
    return SimpleNamespace(
        id=uuid.uuid4(),
        section=section,
        text=text,
        citation_label=label or f"Some Act · Section {section}",
    )


def test_accepts_paragraphs_backed_by_retrieved_sources():
    s138 = source("138")
    result = verify(
        [GeneratedParagraph("Dishonour of a cheque is an offence under Section 138.", [s138.id])],
        {s138.id: s138},
    )
    assert result is not None
    assert result.citations == [s138]
    assert result.paragraphs[0].citation_numbers == [1]


def test_numbers_citations_in_order_of_first_use():
    a, b = source("138"), source("142")
    result = verify(
        [GeneratedParagraph("First.", [b.id]), GeneratedParagraph("Second.", [a.id, b.id])],
        {a.id: a, b.id: b},
    )
    assert result is not None
    assert result.citations == [b, a]
    assert [p.citation_numbers for p in result.paragraphs] == [[1], [2, 1]]


def test_rejects_a_paragraph_without_a_citation():
    s = source("138")
    assert verify([GeneratedParagraph("Uncited claim.", [])], {s.id: s}) is None


def test_rejects_a_citation_that_was_not_retrieved():
    s = source("138")
    assert verify([GeneratedParagraph("Claim.", [uuid.uuid4()])], {s.id: s}) is None


def test_rejects_a_section_number_the_cited_source_does_not_support():
    s138 = source("138", text="Dishonour of cheque for insufficiency of funds.")
    paragraph = GeneratedParagraph("Under Section 420 the drawer is liable.", [s138.id])
    assert verify([paragraph], {s138.id: s138}) is None


def test_accepts_a_section_number_found_in_the_cited_text():
    s = source("142", text="Notwithstanding section 138 no court shall take cognizance.")
    paragraph = GeneratedParagraph("Cognizance is limited, subject to Section 138.", [s.id])
    assert verify([paragraph], {s.id: s}) is not None


def test_rejects_an_empty_answer():
    assert verify([], {}) is None
