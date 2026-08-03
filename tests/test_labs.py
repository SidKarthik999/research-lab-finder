from src.ingestion.labs import match_professor


def test_matches_unique_surname():
    professors = [(1, "Stefano Ermon"), (2, "Jane Smith")]
    assert match_professor("Ermon", professors) == 1


def test_ambiguous_surname_without_initial_returns_none():
    professors = [(1, "Stefano Ermon"), (2, "Alice Ermon")]
    assert match_professor("Ermon", professors) is None


def test_first_initial_disambiguates_multiple_same_surname():
    professors = [(1, "Stefano Ermon"), (2, "Alice Ermon")]
    assert match_professor("S. Ermon", professors) == 1
    assert match_professor("A. Ermon", professors) == 2


def test_first_initial_mismatch_excludes_candidate():
    professors = [(1, "Stefano Ermon")]
    assert match_professor("A. Ermon", professors) is None


def test_no_surname_match_returns_none():
    professors = [(1, "Stefano Ermon")]
    assert match_professor("Jane Smith", professors) is None


def test_full_pi_name_with_first_and_last():
    professors = [(1, "Stefano Ermon"), (2, "Jane Smith")]
    assert match_professor("Stefano Ermon", professors) == 1


def test_empty_pi_name_returns_none():
    professors = [(1, "Stefano Ermon")]
    assert match_professor("", professors) is None


def test_empty_professor_list_returns_none():
    assert match_professor("Stefano Ermon", []) is None
