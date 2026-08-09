from backend.institution_types import (
    INSTITUTION_TYPES,
    _RAW_TO_TYPE,
    institution_type_for_classification,
    raw_classifications_for_type,
)


def test_institution_types_has_exactly_four_buckets():
    assert len(INSTITUTION_TYPES) == 4
    assert len(set(INSTITUTION_TYPES)) == 4


def test_every_bucket_has_at_least_one_raw_classification():
    for institution_type in INSTITUTION_TYPES:
        assert raw_classifications_for_type(institution_type), institution_type


def test_every_raw_classification_maps_to_one_of_the_four_buckets():
    for raw, bucket in _RAW_TO_TYPE.items():
        assert bucket in INSTITUTION_TYPES, raw


def test_institution_type_for_classification_known_value():
    assert (
        institution_type_for_classification("Doctoral Universities: Very High Research Activity")
        == "Research Universities"
    )


def test_institution_type_for_classification_missing_value_returns_none():
    assert institution_type_for_classification(None) is None
    assert institution_type_for_classification("") is None


def test_institution_type_for_classification_unrecognized_value_returns_none():
    # Absent beats wrong: a label that isn't in the mapping (e.g. Carnegie
    # revises the taxonomy) should fall through to None, not a guess.
    assert institution_type_for_classification("Some Future Carnegie Label") is None


def test_raw_classifications_for_type_unrecognized_bucket_returns_empty_list():
    assert raw_classifications_for_type("Not A Real Bucket") == []


def test_baccalaureate_associate_variants_both_bucket_with_community_colleges():
    # These two are easy to get wrong since they sound closer to
    # Baccalaureate Colleges (Four-Year) than to Associate's Colleges.
    assert (
        institution_type_for_classification("Baccalaureate/Associate's Colleges: Associate's Dominant")
        == "Associate's & Community Colleges"
    )
    assert (
        institution_type_for_classification(
            "Baccalaureate/Associate's Colleges: Mixed Baccalaureate/Associate's"
        )
        == "Associate's & Community Colleges"
    )


def test_special_focus_research_institution_stays_specialized_not_research_universities():
    # Name collision risk: "Special Focus Four-Year: Research Institution"
    # (e.g. Rockefeller University) must NOT land in Research Universities
    # just because the raw label contains the word "Research".
    assert (
        institution_type_for_classification("Special Focus Four-Year: Research Institution")
        == "Specialized & Professional Schools"
    )
