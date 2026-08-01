-- Ad-hoc queries for searching the populated database.
-- Run with: psql -d research_lab_finder -f database/queries.sql
-- or paste individual queries into `psql -d research_lab_finder`.


-- ============================================================
-- Core search: find labs by research interest
-- ============================================================

-- Search labs by a research topic keyword (e.g. 'neural', 'genetics').
-- This is the main "search by research interest" query.
SELECT
    Lab.id,
    Lab.name AS lab_name,
    Professor.name AS pi_name,
    Professor.email AS pi_email,
    Lab.website,
    string_agg(DISTINCT ResearchTopic.name, ', ') AS topics
FROM Lab
JOIN LabResearchTopic ON LabResearchTopic.lab_id = Lab.id
JOIN ResearchTopic ON ResearchTopic.id = LabResearchTopic.topic_id
LEFT JOIN Professor ON Professor.id = Lab.pi_professor_id
WHERE ResearchTopic.name ILIKE '%neural%'
GROUP BY Lab.id, Professor.name, Professor.email, Lab.website
ORDER BY lab_name;

-- Same search, but only labs with a real (scraped) email on file --
-- i.e. the ones actually ready for a cold email right now.
SELECT
    Lab.name AS lab_name,
    Professor.name AS pi_name,
    Professor.email AS pi_email,
    Lab.website,
    string_agg(DISTINCT ResearchTopic.name, ', ') AS topics
FROM Lab
JOIN LabResearchTopic ON LabResearchTopic.lab_id = Lab.id
JOIN ResearchTopic ON ResearchTopic.id = LabResearchTopic.topic_id
JOIN Professor ON Professor.id = Lab.pi_professor_id
WHERE ResearchTopic.name ILIKE '%machine learning%'
  AND Professor.email IS NOT NULL
GROUP BY Lab.name, Professor.name, Professor.email, Lab.website
ORDER BY lab_name;


-- Search labs by institution + topic together (e.g. "AI labs at Stanford").
SELECT
    Lab.name AS lab_name,
    Professor.name AS pi_name,
    Professor.email AS pi_email,
    ResearchTopic.name AS topic
FROM Lab
JOIN LabResearchTopic ON LabResearchTopic.lab_id = Lab.id
JOIN ResearchTopic ON ResearchTopic.id = LabResearchTopic.topic_id
JOIN Professor ON Professor.id = Lab.pi_professor_id
JOIN Institution ON Institution.id = Professor.institution_id
WHERE Institution.name ILIKE '%Stanford%'
  AND ResearchTopic.name ILIKE '%artificial intelligence%'
ORDER BY lab_name;


-- ============================================================
-- Search by professor / institution
-- ============================================================

-- All labs at a given institution.
SELECT
    Lab.name AS lab_name,
    Professor.name AS pi_name,
    Professor.email AS pi_email
FROM Lab
JOIN Professor ON Professor.id = Lab.pi_professor_id
JOIN Institution ON Institution.id = Professor.institution_id
WHERE Institution.name = 'Massachusetts Institute of Technology'
ORDER BY lab_name;

-- Look up a specific professor by (partial) name, with their lab and contact info.
SELECT
    Professor.name,
    Professor.email,
    Professor.website,
    Professor.orcid,
    Lab.name AS lab_name,
    Lab.website AS lab_website
FROM Professor
LEFT JOIN Lab ON Lab.pi_professor_id = Professor.id
WHERE Professor.name ILIKE '%kaynig%';

-- All publications by a given professor, most recent first.
SELECT
    Publication.title,
    Publication.journal,
    Publication.publication_date,
    Publication.doi,
    Publication.url
FROM Publication
JOIN ProfessorPublication ON ProfessorPublication.publication_id = Publication.id
JOIN Professor ON Professor.id = ProfessorPublication.professor_id
WHERE Professor.name ILIKE '%gavin sherlock%'
ORDER BY Publication.publication_date DESC NULLS LAST;


-- ============================================================
-- Full lab profile (everything needed for a cold email)
-- ============================================================

-- Given a lab id, pull together everything a student needs to reach out:
-- PI contact, lab site/description, topics, and recent publications.
SELECT
    Lab.name AS lab_name,
    Lab.website AS lab_website,
    Lab.description AS lab_description,
    Professor.name AS pi_name,
    Professor.email AS pi_email,
    Professor.website AS pi_website,
    (SELECT string_agg(DISTINCT ResearchTopic.name, ', ')
       FROM LabResearchTopic
       JOIN ResearchTopic ON ResearchTopic.id = LabResearchTopic.topic_id
      WHERE LabResearchTopic.lab_id = Lab.id) AS topics,
    (SELECT string_agg(Publication.title, ' | ' ORDER BY Publication.publication_date DESC)
       FROM ProfessorPublication
       JOIN Publication ON Publication.id = ProfessorPublication.publication_id
      WHERE ProfessorPublication.professor_id = Professor.id
      LIMIT 5) AS recent_publications
FROM Lab
LEFT JOIN Professor ON Professor.id = Lab.pi_professor_id
WHERE Lab.id = 1;


-- ============================================================
-- Data quality / coverage checks
-- ============================================================

-- Overall row counts per table, to sanity-check a fresh ingestion run.
SELECT 'institution' AS table_name, count(*) FROM Institution
UNION ALL SELECT 'professor', count(*) FROM Professor
UNION ALL SELECT 'lab', count(*) FROM Lab
UNION ALL SELECT 'publication', count(*) FROM Publication
UNION ALL SELECT 'research_topic', count(*) FROM ResearchTopic
UNION ALL SELECT 'lab_research_topic', count(*) FROM LabResearchTopic;

-- How many labs are actually enriched (real website/email on the PI) vs.
-- still just the synthetic "<Professor> Lab" placeholder.
SELECT
    count(*) FILTER (WHERE Professor.website IS NOT NULL) AS labs_with_real_website,
    count(*) FILTER (WHERE Professor.email IS NOT NULL) AS labs_with_real_email,
    count(*) AS total_labs
FROM Lab
LEFT JOIN Professor ON Professor.id = Lab.pi_professor_id;

-- Most common research topics, to see what's well-represented in the data
-- (useful for sanity-checking search relevance / picking demo queries).
SELECT ResearchTopic.name, count(*) AS lab_count
FROM LabResearchTopic
JOIN ResearchTopic ON ResearchTopic.id = LabResearchTopic.topic_id
GROUP BY ResearchTopic.name
ORDER BY lab_count DESC
LIMIT 20;

-- Institutions by how many labs were ingested for them (spot-check coverage).
-- NOTE: Professor.institution_id was added after the last full ingestion run --
-- older professor rows won't have it populated until ingestion is re-run.
SELECT Institution.name, count(DISTINCT Lab.id) AS lab_count
FROM Institution
JOIN Professor ON Professor.institution_id = Institution.id
JOIN Lab ON Lab.pi_professor_id = Professor.id
GROUP BY Institution.name
ORDER BY lab_count DESC;
