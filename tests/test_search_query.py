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
    "topic": "Neuroscience",
    "field": "Biology",
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
