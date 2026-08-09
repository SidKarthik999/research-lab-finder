"""Buckets the ~33 granular Carnegie Basic Classification labels
(src/ingestion/carnegie.py's BASIC2021_LABELS) down to four general
institution types for the search filter and result badges.

The raw Carnegie taxonomy distinguishes things like nine different flavors
of "Associate's Colleges" by transfer-vs-technical mix and traditional-vs-
nontraditional student age -- real distinctions Carnegie's own researchers
care about, but far more than a student choosing a search filter needs. This
mapping is presentation/filtering only: Institution.carnegie_classification
keeps storing the raw label, so nothing about the ingested data changes and
the full detail is still there if a future screen wants it.

Pure and DB-free, same "split for testability" pattern as build_search_query
in backend/main.py -- see tests/test_institution_types.py.
"""

RESEARCH_UNIVERSITIES = "Research Universities"
FOUR_YEAR_COLLEGES = "Four-Year Colleges & Universities"
ASSOCIATE_COMMUNITY_COLLEGES = "Associate's & Community Colleges"
SPECIALIZED_SCHOOLS = "Specialized & Professional Schools"

INSTITUTION_TYPES = [
    RESEARCH_UNIVERSITIES,
    FOUR_YEAR_COLLEGES,
    ASSOCIATE_COMMUNITY_COLLEGES,
    SPECIALIZED_SCHOOLS,
]

# Every raw label BASIC2021_LABELS can produce, mapped explicitly rather than
# by prefix matching. Most labels do share a clean prefix ("Associate's
# Colleges: ...", "Special Focus Four-Year: ...") but the two "Baccalaureate/
# Associate's Colleges" variants don't split along any prefix, so an explicit
# table keeps every value unambiguous and lets a genuinely new/unrecognized
# label fall through to None (absent beats wrong) instead of guessing.
_RAW_TO_TYPE = {
    "Associate's Colleges: High Transfer-High Traditional": ASSOCIATE_COMMUNITY_COLLEGES,
    "Associate's Colleges: High Transfer-Mixed Traditional/Nontraditional": ASSOCIATE_COMMUNITY_COLLEGES,
    "Associate's Colleges: High Transfer-High Nontraditional": ASSOCIATE_COMMUNITY_COLLEGES,
    "Associate's Colleges: Mixed Transfer/Career & Technical-High Traditional": ASSOCIATE_COMMUNITY_COLLEGES,
    "Associate's Colleges: Mixed Transfer/Career & Technical-Mixed Traditional/Nontraditional": ASSOCIATE_COMMUNITY_COLLEGES,
    "Associate's Colleges: Mixed Transfer/Career & Technical-High Nontraditional": ASSOCIATE_COMMUNITY_COLLEGES,
    "Associate's Colleges: High Career & Technical-High Traditional": ASSOCIATE_COMMUNITY_COLLEGES,
    "Associate's Colleges: High Career & Technical-Mixed Traditional/Nontraditional": ASSOCIATE_COMMUNITY_COLLEGES,
    "Associate's Colleges: High Career & Technical-High Nontraditional": ASSOCIATE_COMMUNITY_COLLEGES,
    "Special Focus Two-Year: Health Professions": ASSOCIATE_COMMUNITY_COLLEGES,
    "Special Focus Two-Year: Technical Professions": ASSOCIATE_COMMUNITY_COLLEGES,
    "Special Focus Two-Year: Arts & Design": ASSOCIATE_COMMUNITY_COLLEGES,
    "Special Focus Two-Year: Other Fields": ASSOCIATE_COMMUNITY_COLLEGES,
    # Both "Baccalaureate/Associate's" variants go with the two-year bucket
    # rather than the four-year one -- Carnegie groups them as their own
    # basic category adjacent to Associate's Colleges, not to Baccalaureate
    # Colleges, and even the "Mixed" variant has no bachelor's-dominant
    # population to justify splitting it from its "Associate's Dominant"
    # sibling.
    "Baccalaureate/Associate's Colleges: Associate's Dominant": ASSOCIATE_COMMUNITY_COLLEGES,
    "Baccalaureate/Associate's Colleges: Mixed Baccalaureate/Associate's": ASSOCIATE_COMMUNITY_COLLEGES,
    "Doctoral Universities: Very High Research Activity": RESEARCH_UNIVERSITIES,
    "Doctoral Universities: High Research Activity": RESEARCH_UNIVERSITIES,
    "Doctoral/Professional Universities": RESEARCH_UNIVERSITIES,
    "Master's Colleges & Universities: Larger Programs": FOUR_YEAR_COLLEGES,
    "Master's Colleges & Universities: Medium Programs": FOUR_YEAR_COLLEGES,
    "Master's Colleges & Universities: Small Programs": FOUR_YEAR_COLLEGES,
    "Baccalaureate Colleges: Arts & Sciences Focus": FOUR_YEAR_COLLEGES,
    "Baccalaureate Colleges: Diverse Fields": FOUR_YEAR_COLLEGES,
    "Special Focus Four-Year: Faith-Related Institutions": SPECIALIZED_SCHOOLS,
    "Special Focus Four-Year: Medical Schools & Centers": SPECIALIZED_SCHOOLS,
    "Special Focus Four-Year: Other Health Professions Schools": SPECIALIZED_SCHOOLS,
    # Includes "Research Institution" (e.g. Rockefeller University) -- these
    # are single-subject specialized schools, not general research
    # universities, so they stay with the other Special Focus Four-Year
    # labels rather than moving to the Research Universities bucket.
    "Special Focus Four-Year: Research Institution": SPECIALIZED_SCHOOLS,
    "Special Focus Four-Year: Engineering and Other Technology-Related Schools": SPECIALIZED_SCHOOLS,
    "Special Focus Four-Year: Business & Management Schools": SPECIALIZED_SCHOOLS,
    "Special Focus Four-Year: Arts, Music & Design Schools": SPECIALIZED_SCHOOLS,
    "Special Focus Four-Year: Law Schools": SPECIALIZED_SCHOOLS,
    "Special Focus Four-Year: Other Special Focus Institutions": SPECIALIZED_SCHOOLS,
    "Tribal Colleges and Universities": SPECIALIZED_SCHOOLS,
    # "Not classified" (src/ingestion/carnegie.py's basic_code -2) is
    # deliberately absent from this table rather than mapped to a bucket --
    # it's Carnegie's own "doesn't fit the basic taxonomy" value, so there's
    # no general type to bucket it into. Falls through to None below, same
    # as any other unrecognized/missing value.
}


def institution_type_for_classification(raw_classification):
    """Maps a stored Institution.carnegie_classification value to one of the
    four general buckets above. Returns None for a missing or unrecognized
    value -- absent beats wrong, same as everywhere else classification-
    related in this project -- rather than guessing at a bucket."""
    if not raw_classification:
        return None
    return _RAW_TO_TYPE.get(raw_classification)


def raw_classifications_for_type(institution_type):
    """Reverse lookup: every raw Carnegie label that falls into the given
    general bucket, used to build the /api/search SQL filter as an IN list.
    Returns [] for an unrecognized bucket name rather than raising, so a bad
    query param just matches nothing instead of 500ing."""
    return [raw for raw, bucket in _RAW_TO_TYPE.items() if bucket == institution_type]
