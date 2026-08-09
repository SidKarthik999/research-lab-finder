-- AI summary generation (POST /api/professors/{id}/summary) was never
-- logged to LlmUsage: unlike cold-email/resume-import, it has no per-user
-- daily cap and isn't gated behind sign-in at all (see CLAUDE.md Phase 5A --
-- the AI summary is a public page feature, not tied to an account), so
-- there's no guaranteed user_id to attach to the row. This is what admin
-- dashboard's "AI summaries" metric was actually missing -- not a query
-- bug, the events themselves were never being written. Nullable user_id
-- lets a signed-out visitor's summary generation still get counted.
ALTER TABLE LlmUsage ALTER COLUMN user_id DROP NOT NULL;
