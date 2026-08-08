-- Lets a signed-in student bookmark a professor to revisit from their
-- profile page, alongside whatever cold-email draft they've generated for
-- that professor (EmailDraft already exists from Phase 5A; this doesn't
-- duplicate draft storage, just surfaces the latest one per bookmark --
-- see src/database.py::get_bookmarks_for_user).
CREATE TABLE IF NOT EXISTS Bookmark (
    id SERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL,
    professor_id INTEGER NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    FOREIGN KEY (user_id)
        REFERENCES AppUser(id),

    FOREIGN KEY (professor_id)
        REFERENCES Professor(id),

    UNIQUE (user_id, professor_id)
);
