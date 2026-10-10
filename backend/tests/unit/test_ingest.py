from mrcourt.services.ingest import MAX_CHARS, chunk_pages, read_pages


def test_passages_never_cross_a_page_and_stay_a_sensible_size():
    sentence = "The court considered the submissions of both parties carefully. "
    pages = [(1, sentence * 60), (2, "A short second page."), (3, sentence * 25)]
    passages = chunk_pages(pages)
    assert {p.page for p in passages} == {1, 2, 3}
    assert all(len(p.text) <= MAX_CHARS for p in passages)
    assert [p.text for p in passages if p.page == 2] == ["A short second page."]


def test_nothing_is_lost_between_passages():
    words = [f"word{i}" for i in range(1200)]
    passages = chunk_pages([(1, " ".join(words))])
    joined = " ".join(p.text for p in passages)
    assert all(w in joined for w in words)


def test_text_files_are_one_page():
    assert read_pages(b"Hello there, this is a note with enough words in it.", "a.txt", max_pages=10) == [
        (1, "Hello there, this is a note with enough words in it.")
    ]
