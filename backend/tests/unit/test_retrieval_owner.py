from helpers import make_document
from sqlalchemy import select

from mrcourt.models import User
from mrcourt.services.retrieval import retrieve


def _user(db, email):
    return db.scalar(select(User).where(User.email == email))


def test_private_passages_reach_only_their_owner(db):
    rohan = _user(db, "rohan.sharma@example.com")
    anita = _user(db, "anita.sharma@example.com")
    make_document(
        db,
        title="Rohan note",
        citation="Rohan private note",
        kind="note",
        owner=rohan,
        passages=["Zanzibar clause: the limitation for the zanzibar matter is eleven months."],
    )
    db.commit()

    question = "What is the limitation for the zanzibar matter clause?"
    assert [h.source.citation_label for h in retrieve(db, question, rohan)] == ["Rohan private note, page 1"]
    assert retrieve(db, question, anita) == []
    assert retrieve(db, question, None) == []


def test_passages_of_a_document_still_processing_or_failed_are_not_used(db):
    make_document(db, title="Half done", citation="Half done", passages=["Quokka rule about quokka habitats."], status="processing")
    make_document(db, title="Broken", citation="Broken", passages=["Quokka rule about quokka habitats."], status="failed")
    db.commit()
    assert retrieve(db, "Which quokka rule covers quokka habitats?", None) == []


def test_the_passage_that_answers_the_question_ranks_first_in_a_long_document(db):
    filler = "The court considered the submissions of the parties and the documents on record at length."
    make_document(
        db,
        title="Long judgment",
        citation="S.A. 1 of 2020",
        passages=[
            f"{filler} {filler} The appeal was filed by the appellant against the decree.",
            f"{filler} The respondent claimed title to the property through a partition deed dated 1979.",
            f"{filler} {filler} {filler} Costs were left to the parties.",
        ],
    )
    db.commit()
    hits = retrieve(db, "How did the respondent claim title through the partition deed?", None)
    assert hits and hits[0].source.page == 2


def test_unrelated_questions_still_find_nothing(db):
    assert retrieve(db, "What colour is a purple elephant on Tuesday?", None) == []
