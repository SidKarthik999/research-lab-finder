-- Phase 7 (professor-student matching) needs structured signals to compute
-- a deterministic match score against -- StudentProfile's existing fields
-- (level/school/coursework/skills/prior_experience/looking_for) are all
-- free text about the student's background and what they're asking for,
-- none of it a clean "what subject" or "where" signal to compare against a
-- professor's topics/location. `interests` is deliberately separate from
-- `looking_for`: looking_for is about the ask (a few hours/week, summer,
-- remote), interests is the subject matter ("computational biology,
-- robotics"). city/state/country_code mirror Institution's location
-- columns so a match's location component can compare like with like.
--
-- All nullable, same "a student profile can be partially filled" convention
-- as every other StudentProfile column -- see src/database.py's
-- upsert_student_profile (full EXCLUDED replace, not COALESCE).
ALTER TABLE StudentProfile
    ADD COLUMN IF NOT EXISTS interests TEXT,
    ADD COLUMN IF NOT EXISTS city TEXT,
    ADD COLUMN IF NOT EXISTS state TEXT,
    ADD COLUMN IF NOT EXISTS country_code TEXT;
