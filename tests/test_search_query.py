import itertools

import pytest

from backend.main import build_search_query

FILTER_KWARGS = {
    "name": "Smith",
    "text": "optogenetics",
    "institution": "Stanford",
    "city": "Palo Alto",
    "state": "California",
    "country": "US",
    "metro": "nyc",
    "topic": "Neuroscience",
    "field": "Biology",
    "recent_only": True,
    "institution_type": "Research Universities",
}


def placeholder_count(sql):
    # %s is the only psycopg placeholder style used here; %% (a literal
    # percent, e.g. in an ILIKE pattern) must not be miscounted as one.
    return sql.replace("%%", "").count("%s")


@pytest.mark.parametrize(
    "active_filters",
    [
        combo
        for r in range(len(FILTER_KWARGS) + 1)
        for combo in itertools.combinations(FILTER_KWARGS, r)
    ],
)
def test_placeholder_count_matches_param_count_for_every_filter_combination(active_filters):
    kwargs = {key: FILTER_KWARGS[key] for key in active_filters}
    sql, params = build_search_query(**kwargs)
    assert placeholder_count(sql) == len(params)


def test_no_filters_returns_unconditioned_query():
    # WHERE appears unconditionally inside the ranking LATERAL subqueries,
    # so check for the absence of any filter condition instead of "WHERE".
    sql, params = build_search_query(page=1, limit=20)
    assert "Institution.name ILIKE" not in sql
    assert "EXISTS" not in sql
    assert params == [None, None, 20, 0]


def test_offset_computed_from_page_and_limit():
    _, params = build_search_query(page=3, limit=10)
    assert params[-2:] == [10, 20]


def test_name_filter_matches_professor_name_only():
    sql, params = build_search_query(name="Smith", limit=5)
    assert "Professor.name ILIKE" in sql
    assert "%Smith%" in params
    # name shouldn't feed the publication text-rank placeholders
    assert params[0] is None and params[1] is None


def test_text_filter_used_for_where_and_ranking():
    sql, params = build_search_query(text="optogenetics", limit=5)
    assert "EXISTS" in sql
    assert "search_vector" in sql
    # 2x text-rank ranking placeholders + 1x publication EXISTS match, all
    # the raw term (not %-wrapped, since it's a tsquery input, not ILIKE)
    assert params.count("optogenetics") == 3
    assert "%optogenetics%" not in params


def test_topic_filter_uses_exists_clause():
    sql, params = build_search_query(topic="Neuroscience", limit=5)
    assert "EXISTS" in sql
    assert "%Neuroscience%" in params


def test_field_filter_uses_exists_clause():
    sql, params = build_search_query(field="Biology", limit=5)
    assert "EXISTS" in sql
    assert "%Biology%" in params


def test_recent_only_defaults_to_off():
    sql, _ = build_search_query(page=1, limit=20)
    assert "publication_date >=" not in sql


def test_recent_only_uses_exists_clause_with_no_extra_placeholder():
    # A fixed interval baked into the SQL text, not user input, so opting in
    # shouldn't add a %s placeholder -- only the two publication-search rank
    # placeholders (always present) should show up in params.
    sql, params = build_search_query(recent_only=True, limit=5)
    assert "EXISTS" in sql
    assert "publication_date >=" in sql
    assert "INTERVAL" in sql
    assert params == [None, None, 5, 0]


def test_recent_only_combined_with_another_filter_still_matches_placeholder_count():
    sql, params = build_search_query(recent_only=True, topic="Neuroscience", limit=5)
    assert placeholder_count(sql) == len(params)


def test_institution_type_matches_against_raw_classification_list_not_ilike():
    # institution_type is one of the four general buckets in
    # backend/institution_types.py, expanded back into the raw Carnegie
    # labels that fall under it for an ANY() match -- exact values, not
    # ILIKE, since several real Carnegie labels are substrings of each other
    # (e.g. "...High Research Activity" is a substring of "...Very High
    # Research Activity") and ILIKE would silently conflate different tiers.
    sql, params = build_search_query(institution_type="Research Universities", limit=5)
    assert "Institution.carnegie_classification = ANY(%s)" in sql
    assert "Institution.carnegie_classification ILIKE" not in sql
    (raw_list,) = [p for p in params if isinstance(p, list)]
    assert "Doctoral Universities: Very High Research Activity" in raw_list
    assert "Doctoral Universities: High Research Activity" in raw_list
    assert "Master's Colleges & Universities: Larger Programs" not in raw_list


def test_unrecognized_institution_type_matches_nothing_not_everything():
    sql, params = build_search_query(institution_type="Not A Real Bucket", limit=5)
    assert "Institution.carnegie_classification = ANY(%s)" in sql
    (raw_list,) = [p for p in params if isinstance(p, list)]
    assert raw_list == []


def test_metro_filter_matches_curated_city_state_pairs():
    sql, params = build_search_query(metro="nyc", limit=5)
    assert "Institution.city ILIKE" in sql
    assert "Institution.state ILIKE" in sql
    assert "%Brooklyn%" in params
    assert "%New York%" in params


def test_metro_filter_placeholder_count_matches_params():
    sql, params = build_search_query(metro="nyc", limit=5)
    assert placeholder_count(sql) == len(params)


def test_unrecognized_metro_matches_nothing_not_everything():
    sql, params = build_search_query(metro="not_a_real_metro", limit=5)
    assert "FALSE" in sql
