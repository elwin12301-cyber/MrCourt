from mrcourt.services.references import Reference, match, parse_references


def _sections(question: str) -> list[tuple[str, str | None]]:
    return [(r.number, r.act) for r in parse_references(question) if r.kind == "section"]


def test_the_ways_people_write_a_section() -> None:
    assert _sections("What does Section 379 IPC say?") == [("379", "IPC")]
    assert _sections("punishment under sec. 420 of the Indian Penal Code") == [("420", "IPC")]
    assert _sections("is s.379 bailable?") == [("379", None)]
    assert _sections("arrested u/s 302") == [("302", None)]
    assert _sections("379 IPC and theft") == [("379", "IPC")]
    assert _sections("section 303 BNS") == [("303", "BNS")]
    assert _sections("Section 138 of the NI Act") == [("138", "NI")]
    assert _sections("section 53A transfer of property") == [("53A", "TPA")]


def test_articles_and_cases() -> None:
    refs = parse_references("Explain Article 21 and art. 14")
    assert [(r.kind, r.number) for r in refs] == [("article", "21"), ("article", "14")]
    case = parse_references("Summarise W.P. No. 11944 of 2013")[0]
    assert (case.kind, case.case_type, case.number, case.year) == ("case", "WP", "11944", "2013")
    assert parse_references("WP 11944/2013")[0].number == "11944"
    assert parse_references("what happened in O.S. 581?")[0].case_type == "OS"
    assert parse_references("CNR TNCH010012342019")[0].cnr == "TNCH010012342019"


def test_years_and_pages_are_not_references() -> None:
    assert parse_references("What happened in 2013 on page 21?") == []
    assert parse_references("how have courts decided bail since 1990") == []


def test_a_passage_is_or_mentions_the_section() -> None:
    ref = Reference("section", "138", "NI")
    assert match(ref, instrument="Negotiable Instruments Act, 1881", section="138", label="", text="") == "exact"
    assert match(ref, instrument="Negotiable Instruments Act (notes)", section=None, label="", text="Under Section 138 the drawer ...") == "mentions"
    assert match(ref, instrument="Indian Penal Code (IPC)", section="138", label="", text="") is None  # another Act


def test_old_and_new_codes_are_not_the_same() -> None:
    bns = Reference("section", "379", "BNS")
    assert match(bns, instrument="Indian Penal Code (IPC)", section="379", label="", text="") is None


def test_an_article_heading_counts_but_a_list_of_contents_does_not() -> None:
    article = Reference("article", "21", "CONSTITUTION")
    body = "THE CONSTITUTION OF INDIA\n21. Protection of life and personal liberty.—No person shall be deprived"
    contents = "17. Abolition of Untouchability. 18. Abolition of titles. 19. Protection of certain rights 20. Protection in respect 21. Protection of life 22. Protection against arrest"
    assert match(article, instrument="The Constitution of India", section=None, label="", text=body) == "mentions"
    assert match(article, instrument="The Constitution of India", section=None, label="", text=contents) is None


def test_a_case_number_matches_its_document() -> None:
    ref = parse_references("W.P. 11944/2013")[0]
    assert match(ref, instrument="WP 11944-2013 Order", section=None, label="", text="W.P.No.11944 of 2013 ...") == "exact"
    assert match(ref, instrument="judgement", section=None, label="", text="O.S. No. 581 of 2010") is None


def test_a_case_number_matches_through_the_documents_mapped_number() -> None:
    ref = parse_references("What was decided in S.A. No. 4410 of 2019?")[0]
    later_page = dict(instrument="judgement", section=None, label="judgement.pdf, page 9", text="The appeal is allowed.")
    assert match(ref, **later_page) is None
    assert match(ref, **later_page, case_number="S.A. 4410/2019") == "exact"
    assert match(ref, **later_page, case_number="S.A. 4411/2019") is None
