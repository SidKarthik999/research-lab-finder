-- Phase 1: full-text search over the 23k+ Publication abstracts already
-- stored and currently unused. A GENERATED column keeps the tsvector in
-- sync automatically on every insert/update -- no trigger to maintain.

ALTER TABLE Publication
    ADD COLUMN IF NOT EXISTS search_vector tsvector
    GENERATED ALWAYS AS (
        setweight(to_tsvector('english', coalesce(title, '')), 'A') ||
        setweight(to_tsvector('english', coalesce(abstract, '')), 'B')
    ) STORED;

CREATE INDEX IF NOT EXISTS idx_publication_search_vector
    ON Publication USING GIN (search_vector);
