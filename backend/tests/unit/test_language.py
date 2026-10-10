from mrcourt.services.language import detect, keyword_only_notice, source_language_note


def test_scripts_are_recognised():
    assert detect("What is Section 138?") == "English"
    assert detect("மேல்முறையீட்டாளர் யார்?") == "Tamil"
    assert detect("अपीलकर्ता कौन है?") == "Hindi"
    assert detect("Section 138 மற்றும் NI Act") in {"Tamil", "English"}
    assert detect("") == "English" and detect("1234 !!") == "English"


def test_the_note_names_the_sources_language_only_when_it_differs():
    assert source_language_note("மேல்முறையீட்டாளர் யார்?", ["The appellant is Fr. Backiyasamy."]) == "The sources are in English."
    assert source_language_note("Who is the appellant?", ["The appellant is Fr. Backiyasamy."]) is None
    mixed = source_language_note("Who is the appellant?", ["The appellant.", "மேல்முறையீட்டாளர்"])
    assert mixed == "The sources are in English and Tamil."


def test_keyword_only_mode_is_honest_about_non_english_questions():
    assert "needs meaning-based search" in keyword_only_notice("மேல்முறையீட்டாளர் யார்?")
    assert keyword_only_notice("Who is the appellant?") is None
