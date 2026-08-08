from src.ingestion.carnegie import (
    best_deterministic_match,
    build_city_index,
    build_llm_match_prompt,
    jaccard,
    match_candidates,
    name_tokens,
    normalize_city,
)


def test_normalize_city_strips_punctuation_and_case():
    assert normalize_city("St. Louis") == "stlouis"
    assert normalize_city("New York") == "newyork"
    assert normalize_city(None) == ""


def test_name_tokens_drops_stopwords_and_punctuation():
    assert name_tokens("The University of Chicago") == {"university", "chicago"}
    assert name_tokens("St. Francis College") == {"st", "francis", "college"}


def test_jaccard_identical_sets_is_one():
    assert jaccard({"a", "b"}, {"a", "b"}) == 1.0


def test_jaccard_disjoint_sets_is_zero():
    assert jaccard({"a"}, {"b"}) == 0.0


def test_jaccard_empty_set_is_zero_not_a_crash():
    assert jaccard(set(), {"a"}) == 0.0
    assert jaccard(set(), set()) == 0.0


CARNEGIE_RECORDS = [
    {"unitid": 1, "name": "University of Cincinnati", "city": "Cincinnati", "state": "OH", "classification": "R1"},
    {"unitid": 2, "name": "ATA College-Cincinnati", "city": "Cincinnati", "state": "OH", "classification": "Special Focus"},
    {"unitid": 3, "name": "University of Minnesota-Twin Cities", "city": "Minneapolis", "state": "MN", "classification": "R1"},
    {"unitid": 4, "name": "Rutgers University-Newark", "city": "Newark", "state": "NJ", "classification": "R2"},
]


def test_build_city_index_groups_by_normalized_city():
    index = build_city_index(CARNEGIE_RECORDS)
    assert len(index[normalize_city("Cincinnati")]) == 2
    assert len(index[normalize_city("Newark")]) == 1


def test_match_candidates_empty_when_city_has_no_carnegie_institutions():
    index = build_city_index(CARNEGIE_RECORDS)
    assert match_candidates("Some College", "Nowhere", index) == []


def test_match_candidates_ranks_best_match_first():
    # Regression case for the false positive found testing against real
    # data: plain string similarity matched "University of Cincinnati" to
    # "ATA College-Cincinnati" -- token-Jaccard, scored here, must not.
    index = build_city_index(CARNEGIE_RECORDS)
    scored = match_candidates("University of Cincinnati", "Cincinnati", index)
    assert scored[0][0]["name"] == "University of Cincinnati"
    assert scored[0][1] > scored[1][1]


def test_best_deterministic_match_accepts_above_threshold():
    index = build_city_index(CARNEGIE_RECORDS)
    match = best_deterministic_match("University of Cincinnati", "Cincinnati", index)
    assert match is not None
    assert match[0]["name"] == "University of Cincinnati"


def test_best_deterministic_match_rejects_weak_match_regardless_of_ranking():
    # "St. Francis College" only shares the word "college" with any
    # Cincinnati-area candidate here -- ranking first isn't enough, it has
    # to clear the threshold too.
    index = build_city_index(CARNEGIE_RECORDS)
    match = best_deterministic_match("St. Francis College", "Cincinnati", index)
    assert match is None


def test_best_deterministic_match_none_when_no_city_candidates():
    index = build_city_index(CARNEGIE_RECORDS)
    assert best_deterministic_match("Some College", "Nowhere", index) is None


def test_llm_prompt_lists_only_the_given_shortlist_ids():
    shortlist = [(CARNEGIE_RECORDS[0], 0.5), (CARNEGIE_RECORDS[1], 0.3)]
    prompt = build_llm_match_prompt("University of Cincinnati", "Cincinnati", "OH", shortlist)
    assert "1: University of Cincinnati" in prompt
    assert "2: ATA College-Cincinnati" in prompt
    assert "Rutgers" not in prompt


def test_llm_prompt_handles_missing_location():
    prompt = build_llm_match_prompt("Some College", None, None, [])
    assert "(unknown city)" in prompt
    assert "(unknown state)" in prompt
