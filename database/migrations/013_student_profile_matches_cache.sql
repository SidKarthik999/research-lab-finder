-- Smart search (Phase 7) result cache. GET /api/me/matches makes an OpenAI
-- call (2-8s) that the DB retrieval around it does not -- so a repeat
-- search with the same inputs (toggling the checkbox, visiting a professor
-- and coming back) should return the stored result instantly instead of
-- regenerating.
--
-- matches_key is a hash of the inputs that affect the result (profile
-- interests + location, plus any typed search filters) -- see
-- matches_cache_key() in backend/matching.py. A hit requires the key to
-- match AND matches_generated_at to be within the TTL; editing the profile
-- changes the key, and GET /api/me/matches?refresh=1 forces past it.
--
-- All nullable, same "a profile row can be partially populated" convention
-- as every other StudentProfile column.
ALTER TABLE StudentProfile
    ADD COLUMN IF NOT EXISTS matches_json TEXT,
    ADD COLUMN IF NOT EXISTS matches_key TEXT,
    ADD COLUMN IF NOT EXISTS matches_generated_at TIMESTAMP;
