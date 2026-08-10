-- Lets an admin mark a flagged report as handled without deleting it (see
-- DELETE /api/admin/flags/{id}, added earlier -- sometimes you want a
-- record that something was reported and dealt with, not just gone).
-- resolved_at is nullable rather than a boolean so it also records *when*,
-- for free -- NULL means still open, same "absent beats wrong" convention
-- used elsewhere in this schema (e.g. Professor.ai_summary).
ALTER TABLE ProfessorFlag ADD COLUMN IF NOT EXISTS resolved_at TIMESTAMP;
