-- Phase 1: reintroduce ResearchTopic, this time populated from each
-- professor's own OpenAlex Author record (Author.topics -- derived from that
-- author's own works) rather than reconstructed from Works authorships. See
-- CLAUDE.md / docs/ROADMAP.md Phase 1 for why this is safe where the
-- original Works-based approach was not.

CREATE TABLE IF NOT EXISTS ResearchTopic (
    id SERIAL PRIMARY KEY,
    openalex_id TEXT NOT NULL UNIQUE,
    name TEXT NOT NULL,
    subfield TEXT,
    field TEXT,
    domain TEXT,
    source TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS ProfessorTopic (
    professor_id INTEGER NOT NULL,
    topic_id INTEGER NOT NULL,
    -- OpenAlex's Author.topics doesn't expose a normalized "score" -- it
    -- gives a works_count per topic (how many of the author's own works are
    -- tagged with it), already ordered most-relevant-first. That count is
    -- what we rank on.
    works_count INTEGER,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    PRIMARY KEY (professor_id, topic_id),

    FOREIGN KEY (professor_id)
        REFERENCES Professor(id),

    FOREIGN KEY (topic_id)
        REFERENCES ResearchTopic(id)
);
