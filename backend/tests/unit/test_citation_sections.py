import uuid
from dataclasses import dataclass

from mrcourt.services.citations import GeneratedParagraph, verify


@dataclass
class Source:
    text: str
    citation_label: str = "Indian Penal Code, page 1"
    section: str | None = None
    id: uuid.UUID = uuid.uuid4()


def _ok(text: str) -> bool:
    source = Source(text, id=uuid.uuid4())
    return verify([GeneratedParagraph(text, [source.id])], {source.id: source}) is not None


def test_a_passage_that_says_sections_in_the_plural_supports_itself():
    assert _ok("Murder is defined in sections 299 and 300 of the Indian Penal Code.")


def test_article_numbers_with_letters_are_read_whole():
    assert _ok("Articles 243ZA and the following apply to municipalities. See Article 243ZA.")


def test_a_section_number_the_source_does_not_contain_is_still_refused():
    source = Source("Theft is defined in section 378.", id=uuid.uuid4())
    invented = GeneratedParagraph("Theft is punished under section 379.", [source.id])
    assert verify([invented], {source.id: source}) is None
