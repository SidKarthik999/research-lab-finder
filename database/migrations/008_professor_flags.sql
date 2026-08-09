-- Lets any visitor report a data-quality issue on a professor's page (wrong
-- person, wrong institution, dead link, ...) -- ingestion is automated
-- (OpenAlex + ORCID enrichment, see CLAUDE.md), so mistakes are expected,
-- and there was previously no way to report one short of emailing the site
-- owner directly. No account required to submit -- reporting a mistake
-- shouldn't be gated behind a signup -- so user_id is nullable and only
-- set when the reporter happens to be signed in already.
CREATE TABLE IF NOT EXISTS ProfessorFlag (
    id SERIAL PRIMARY KEY,
    professor_id INTEGER NOT NULL,
    user_id INTEGER,
    -- Checkbox reason ids from backend/flags.py's FLAG_REASONS (e.g.
    -- "wrong_person"), not the display label -- keeps this table stable if
    -- a label's wording changes later.
    reasons TEXT[] NOT NULL DEFAULT '{}',
    details TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    FOREIGN KEY (professor_id)
        REFERENCES Professor(id),

    FOREIGN KEY (user_id)
        REFERENCES AppUser(id)
);
