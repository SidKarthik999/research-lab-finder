-- Ad-hoc queries for searching the populated database.
-- Run with: psql -d research_lab_finder -f database/queries.sql
-- or paste individual queries into `psql -d research_lab_finder`.
--
-- Barebones schema (Institution + Professor only) -- see CLAUDE.md.


-- ============================================================
-- Core search: find professors by name / institution / location
-- ============================================================

-- Look up a specific professor by (partial) name, with their institution.
SELECT
    Professor.name,
    Professor.email,
    Professor.website,
    Professor.orcid,
    Institution.name AS institution_name,
    Institution.city,
    Institution.state,
    Institution.country_code
FROM Professor
LEFT JOIN Institution ON Institution.id = Professor.institution_id
WHERE Professor.name ILIKE '%kaynig%';

-- All professors at a given institution.
SELECT
    Professor.name,
    Professor.email,
    Professor.website,
    Professor.orcid
FROM Professor
JOIN Institution ON Institution.id = Professor.institution_id
WHERE Institution.name = 'Massachusetts Institute of Technology'
ORDER BY Professor.name;

-- Professors by location (city/state/country come from the institution).
SELECT
    Professor.name,
    Institution.name AS institution_name,
    Institution.city,
    Institution.state,
    Institution.country_code
FROM Professor
JOIN Institution ON Institution.id = Professor.institution_id
WHERE Institution.state ILIKE '%California%'
ORDER BY Institution.name, Professor.name;


-- ============================================================
-- Data quality / coverage checks
-- ============================================================

-- Overall row counts, to sanity-check a fresh ingestion run.
SELECT 'institution' AS table_name, count(*) FROM Institution
UNION ALL SELECT 'professor', count(*) FROM Professor;

-- Professors missing an institution link (should be rare/zero after the
-- last_known_institutions.id-based ingestion).
SELECT count(*) FROM Professor WHERE institution_id IS NULL;

-- Institutions by how many professors were ingested for them.
SELECT Institution.name, count(Professor.id) AS professor_count
FROM Institution
LEFT JOIN Professor ON Professor.institution_id = Institution.id
GROUP BY Institution.name
ORDER BY professor_count DESC;
