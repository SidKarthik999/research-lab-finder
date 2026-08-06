-- Phase 5A: accounts, student profiles, cached AI summaries, and email
-- drafts. See CLAUDE.md / docs/ROADMAP.md Phase 5A for the reasoning.
--
-- Auth is multi-provider from the start (Google alongside email/password),
-- so the account and the login method are separate tables: AppUser is the
-- person, AuthIdentity is one row per way they can sign in. This lets the
-- same person link a Google identity and a password identity to one
-- AppUser, and lets a future provider (Apple, GitHub, ...) be a new
-- `provider` value rather than a schema change.
--
-- AuthIdentity.provider_user_id is NOT NULL: for the "password" provider
-- this holds the account's own email as its identity key, so the
-- UNIQUE(provider, provider_user_id) constraint also enforces "one password
-- identity per email" without a separate index.

CREATE TABLE IF NOT EXISTS AppUser (
    id SERIAL PRIMARY KEY,
    email TEXT NOT NULL UNIQUE,
    email_verified BOOLEAN NOT NULL DEFAULT FALSE,
    name TEXT,
    avatar_url TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS AuthIdentity (
    id SERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL,
    provider TEXT NOT NULL,
    provider_user_id TEXT NOT NULL,
    -- Only set for provider = 'password'; NULL for OAuth providers, which
    -- never hold a credential we manage.
    password_hash TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    FOREIGN KEY (user_id)
        REFERENCES AppUser(id),

    UNIQUE (provider, provider_user_id)
);

CREATE TABLE IF NOT EXISTS StudentProfile (
    user_id INTEGER PRIMARY KEY,
    level TEXT,
    school TEXT,
    graduation_year INTEGER,
    coursework TEXT,
    skills TEXT,
    prior_experience TEXT,
    looking_for TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    FOREIGN KEY (user_id)
        REFERENCES AppUser(id)
);

CREATE TABLE IF NOT EXISTS EmailDraft (
    id SERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL,
    professor_id INTEGER NOT NULL,
    body TEXT NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    FOREIGN KEY (user_id)
        REFERENCES AppUser(id),

    FOREIGN KEY (professor_id)
        REFERENCES Professor(id)
);

-- Cached AI summary, generated lazily on first detail-page view rather than
-- for all professors at ingest (most are never viewed). generated_at is
-- separate from updated_at so a future re-generation pass can find stale
-- summaries without also matching unrelated Professor edits.
ALTER TABLE Professor
    ADD COLUMN IF NOT EXISTS ai_summary TEXT,
    ADD COLUMN IF NOT EXISTS ai_summary_generated_at TIMESTAMP;
