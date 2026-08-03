from src.ingestion.openalex import prefer_full_name


def test_expands_bare_initial_to_matching_full_name():
    assert prefer_full_name("A. Roodman", ["Aaron Roodman"]) == "Aaron Roodman"


def test_ignores_alternative_with_same_surname_but_different_first_initial():
    assert prefer_full_name("A. Roodman", ["Brian Roodman"]) == "A. Roodman"


def test_leaves_already_full_name_untouched_even_with_unrelated_alternatives():
    # "Ying Liu"'s alternatives are a disambiguation cluster of unrelated
    # people, not spelling variants -- since the display name has no bare
    # initial token, it should never be touched.
    assert (
        prefer_full_name("Ying Liu", ["Wei Liu", "Ming Liu", "Y. Liu"])
        == "Ying Liu"
    )


def test_ignores_alternative_with_different_surname():
    assert prefer_full_name("A. Roodman", ["Aaron Smith"]) == "A. Roodman"


def test_ignores_alternative_that_is_still_initials():
    assert prefer_full_name("A. Roodman", ["A. R. Roodman"]) == "A. Roodman"


def test_no_alternatives_returns_original():
    assert prefer_full_name("A. Roodman", []) == "A. Roodman"
    assert prefer_full_name("A. Roodman", None) == "A. Roodman"


def test_single_token_name_is_returned_unchanged():
    assert prefer_full_name("Cher", ["Cherilyn Sarkisian"]) == "Cher"


def test_prefers_properly_cased_candidate_over_all_caps_duplicate():
    assert (
        prefer_full_name("A. Roodman", ["AARON ROODMAN", "Aaron Roodman"])
        == "Aaron Roodman"
    )


def test_prefers_shortest_candidate_when_multiple_properly_cased_match():
    assert (
        prefer_full_name(
            "K.-Y. Wang", ["Kai-Yuan Wang", "Kai-Yuan Xavier Wang"]
        )
        == "Kai-Yuan Wang"
    )


def test_compound_initial_token_expands_correctly():
    assert prefer_full_name("M.P. Smith", ["Mary Patricia Smith"]) == "Mary Patricia Smith"
