-- Phase 3: Institution-level classification, matched against the real
-- Carnegie Classification of Institutions of Higher Education (ACE /
-- Indiana University), not a heuristic derived from our own data. See
-- src/ingestion/carnegie.py for the matching pipeline and CLAUDE.md for the
-- reasoning behind the two-tier (deterministic + bounded LLM) approach.
--
-- carnegie_unitid is the source dataset's own IPEDS UnitID for the matched
-- row -- kept so a re-run can look up "did this institution's match change"
-- without re-deriving everything from scratch, and so a wrong match found
-- later can be traced back to exactly which Carnegie row caused it.
--
-- carnegie_match_method records how the match was made ('token_match' for
-- the deterministic city + token-overlap pass, 'llm' for the bounded
-- shortlist-only LLM pass) -- same provenance-tracking convention as
-- Professor.source/Institution.source elsewhere in this schema, since a
-- wrong LLM-assisted match should be easy to identify and reconsider
-- separately from a wrong deterministic one.
ALTER TABLE Institution
    ADD COLUMN IF NOT EXISTS carnegie_classification TEXT,
    ADD COLUMN IF NOT EXISTS carnegie_unitid TEXT,
    ADD COLUMN IF NOT EXISTS carnegie_match_method TEXT;
