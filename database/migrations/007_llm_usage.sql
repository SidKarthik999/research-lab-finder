-- Tracks every LLM-invoking action a student actually triggers (cold-email
-- generation, resume import) so a per-user daily cap can be enforced --
-- see docs/ROADMAP.md Phase 6.4. Deliberately its own table rather than
-- counting EmailDraft rows: EmailDraft only covers cold emails, not resume
-- import, and coupling the cap to that table's shape would break if
-- EmailDraft's own semantics ever change. DB-backed rather than an
-- in-process counter (unlike backend/rate_limit.py's auth rate limiting)
-- because this is a real spend guard against actual OpenAI cost, and it
-- needs to survive a Render free-tier cold start mid-day, not just reset.
CREATE TABLE IF NOT EXISTS LlmUsage (
    id SERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL,
    kind TEXT NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    FOREIGN KEY (user_id)
        REFERENCES AppUser(id)
);

CREATE INDEX IF NOT EXISTS idx_llmusage_user_kind_created ON LlmUsage(user_id, kind, created_at);
