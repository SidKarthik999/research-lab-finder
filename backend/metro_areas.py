# Curated metro-area city lists backing the "Near" location presets on the
# search page. A single city+state ILIKE match (the old preset behavior) only
# matched the literal named city, so "Near NYC" missed the boroughs and inner
# suburbs anyone would actually consider "near New York City" (Brooklyn,
# Jersey City, ...). Each entry here is a (city, state) pair checked against
# the real Institution/Professor data (not guessed) so a preset click doesn't
# land on an empty results page -- and state is paired with city because
# several of these city names collide with unrelated places elsewhere in the
# country (e.g. "Newark" also exists in New Jersey and Ohio; "Newton" also
# exists in New Jersey) -- see cities_for_metro()'s query for the exact match
# semantics, including the blank-state fallback -- built into
# build_search_query's metro handling in backend/main.py.
METRO_AREAS = {
    "nyc": [
        ("New York", "New York"),
        ("Brooklyn", "New York"),
        ("The Bronx", "New York"),
        ("Staten Island", "New York"),
        ("Long Island City", "New York"),
        ("New Rochelle", "New York"),
        ("Hempstead", "New York"),
        ("Hoboken", "New Jersey"),
        ("Jersey City", "New Jersey"),
    ],
    "chicago": [
        ("Chicago", "Illinois"),
        ("Evanston", "Illinois"),
        ("Naperville", "Illinois"),
        ("Elmhurst", "Illinois"),
        ("Downers Grove", "Illinois"),
        ("River Forest", "Illinois"),
        ("Lisle", "Illinois"),
        ("Elgin", "Illinois"),
        ("Joliet", "Illinois"),
        ("Romeoville", "Illinois"),
        ("University Park", "Illinois"),
    ],
    "los_angeles": [
        ("Los Angeles", "California"),
        ("Pasadena", "California"),
        ("Santa Monica", "California"),
        ("Whittier", "California"),
        ("Cerritos", "California"),
        ("Fullerton", "California"),
        ("Rosemead", "California"),
        ("Santa Clarita", "California"),
        ("Norwalk", "California"),
        ("Cypress", "California"),
        ("Riverside", "California"),
        ("Irvine", "California"),
        ("Santa Ana", "California"),
        ("Long Beach", "California"),
        ("Pomona", "California"),
    ],
    "boston": [
        ("Boston", "Massachusetts"),
        ("Cambridge", "Massachusetts"),
        ("Medford", "Massachusetts"),
        ("Brookline", "Massachusetts"),
        ("Waltham", "Massachusetts"),
        ("Newton", "Massachusetts"),
        ("Quincy", "Massachusetts"),
        ("Milton", "Massachusetts"),
        ("Needham", "Massachusetts"),
        ("Weston", "Massachusetts"),
        ("Framingham", "Massachusetts"),
    ],
    "philadelphia": [
        ("Philadelphia", "Pennsylvania"),
        ("Radnor", "Pennsylvania"),
        ("Haverford", "Pennsylvania"),
        ("Collegeville", "Pennsylvania"),
        ("Chester", "Pennsylvania"),
        ("Allentown", "Pennsylvania"),
        ("Bethlehem", "Pennsylvania"),
        ("Newark", "Delaware"),
        ("Camden", "New Jersey"),
    ],
}

# Frontend-facing labels for the same presets -- kept here rather than only
# in frontend/views/search.js so the id <-> label mapping has one source of
# truth; GET /api/metro-areas serves this list the same way
# /api/institution-types serves INSTITUTION_TYPES.
METRO_AREA_LABELS = {
    "nyc": "New York, NY",
    "chicago": "Chicago, IL",
    "los_angeles": "Los Angeles, CA",
    "boston": "Boston, MA",
    "philadelphia": "Philadelphia, PA",
}


def cities_for_metro(metro):
    """Expands a metro id into its (city, state) pairs, or [] if unrecognized
    -- an unrecognized id should match nothing, not everything."""
    return METRO_AREAS.get(metro, [])
