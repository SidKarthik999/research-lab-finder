# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project overview

Research Lab Finder is an early-stage platform for discovering academic research labs by research interest, location, institution, and publications. Data is sourced from OpenAlex and stored in PostgreSQL. `backend/` holds a FastAPI search API and `frontend/` a plain HTML/CSS/JS SPA that consumes it; `docs/` is still a placeholder. No LLM functionality is wired in yet — search is pure SQL filtering.

**Current state is deliberately barebones**: the schema and ingestion pipeline cover `Institution`, `Professor`, and `Publication`. `Lab`, `ResearchTopic`, `Department`, and their junction tables were dropped (2026-08-01) after the original Works-based ingestion produced widespread misattribution (co-authors on a work got tagged with that work's institution even when they belonged elsewhere) and a pile of synthetic/junk `Lab` rows. Those tables are meant to come back in a future phase, once professor↔institution attribution is trustworthy — see "Ingestion pipeline" below for the corrected method and don't reintroduce the Works-based approach when rebuilding them. `Publication` came back first (also 2026-08-01) because it hangs safely off already-attributed `Professor` rows rather than being the thing attribution was derived from.

Future goals (from README, not yet built beyond the MVP search UI): labs and topics layered back on top of correctly-attributed professors/publications, and LLM-based lab summaries / cold-email generation. The backend is intentionally structured so an `/api/*` endpoint calling an LLM can be added later without touching the search path.

## Environment setup

The project uses a conda environment defined in `environment.yml`:

```
conda env create -f environment.yml
conda activate researchlabfinder
```

Dependencies are pinned via conda + pip (`pyalex`, `python-dotenv`, `psycopg`, `fastapi`, `uvicorn`). There is no `requirements.txt` — `environment.yml` is the source of truth.

Secrets (e.g. `OPENALEX_API_KEY`) live in a local `.env` file, loaded via `python-dotenv`. `.env` is gitignored — never commit it.

## Database

- PostgreSQL database name: `research_lab_finder`. Connection is hardcoded in `src/database.py::get_connection()` (dbname + local user, no host/password — assumes a local Postgres instance with peer/trust auth).
- Schema changes go through numbered, additive migrations in `database/migrations/` (`001_initial_schema.sql`, …), applied with `python -m database.migrate` (or `make migrate`). `database/migrate.py` tracks applied versions in a `schema_migrations` table and applies whatever's pending, in order, each in its own transaction. Migration files use `CREATE TABLE IF NOT EXISTS` (and similarly idempotent DDL) so re-running is always safe. Ad-hoc queries live in `database/queries.sql`.
- `database/schema_full.sql` is the **destructive** full-rebuild version (`DROP TABLE ... CASCADE` then recreate everything) — reference/fresh-install only. Never run it against a database with ingested data; use migrations instead. Run `make backup` (a `pg_dump` into the gitignored `database/backups/`) before any schema change to a database you care about.
- Core entity tables: `Institution`, `Professor` (`Professor.institution_id` → `Institution.id`), `Publication`, joined by `ProfessorPublication`. Location fields (`city`, `state`, `country_code`) live on `Institution`, not `Professor` — a professor's location is their institution's location.
- Rows carry a `source` column (e.g. `"OpenAlex"`) plus `created_at`/`updated_at`, to distinguish ingested vs. hand-seeded data.
- Upserts follow a consistent pattern: `INSERT ... ON CONFLICT (<unique_key>) DO UPDATE SET updated_at = CURRENT_TIMESTAMP RETURNING id`, keyed off natural unique identifiers (`openalex_id` or `ror_id`). Follow this pattern for any new insert function in `src/database.py`.
- Backups of the pre-cleanup (Lab/Publication-era) database live in `database/backups/` (gitignored) in case old data is ever needed for reference while rebuilding those features.

## Ingestion pipeline

`src/ingestion/openalex.py` wraps the `pyalex` client to pull data from OpenAlex and insert it via `src/database.py`:

- `search_institution(name)` — looks up a single institution by name via OpenAlex search.
- `get_top_us_institutions(limit)` — top US educational institutions by works count, used to pick which institutions to ingest.
- `insert_openalex_institution(institution)` — upserts one institution.
- `get_professors_at_institution(openalex_institution_id, limit)` / `insert_openalex_professor(author, institution_id)` / `insert_professors_from_institution(authors, institution_id)` — fetch and insert professors.
- `ingest_institution(institution_name, limit)` — the end-to-end driver: search + insert the institution, then fetch + insert its professors.

**Attribution method (important — don't regress this):** professors are fetched via `pyalex.Authors().filter(last_known_institutions={"id": openalex_institution_id})`, which asks OpenAlex "who currently works at this institution" directly. The *previous* approach fetched Works affiliated with an institution and tagged every co-author on those works with that institution — this mislabeled co-authors who actually belonged to a completely different university, which was the root cause of the misattributed labs found during testing. Any future ingestion of Publications/Labs/Topics should hang off of already-attributed `Professor` rows (e.g. "get this professor's works"), not reconstruct attribution from Works' authorships.

When adding a new ingestion entity, mirror this shape: a `search_*`/`get_*` fetch function, an `insert_openalex_*` mapper that translates the OpenAlex JSON shape into the `insert_*` call in `src/database.py`, and (if bulk) an `insert_*_from_*` driver with per-item try/except so one bad record doesn't abort the batch.

Scripts are run directly (`if __name__ == "__main__":` blocks double as manual test harnesses) — there is no CLI framework or task runner yet. `openalex.py`'s `__main__` block runs the full institution list (`get_top_us_institutions(100)`) — accuracy was verified against an 8-institution test batch first.

### Name quality (`prefer_full_name` in `openalex.py`)

OpenAlex's `display_name_alternatives` for a common surname is often a disambiguation cluster of *unrelated* people, not spelling variants of one person (e.g. "Ying Liu"'s alternatives include dozens of different real people also named some variant of "Liu"). `prefer_full_name()` only attempts expansion when the stored name actually looks like bare initials (`INITIAL_TOKEN`, which also matches compound forms like "K.-Y." or "M.P."), and only accepts an alternative that shares the surname and whose other tokens start with the same initials — this is what lets "A. Roodman" safely become "Aaron Roodman" while leaving "Yi-Xiang Wang" (already a full name) untouched.

### ORCID-based name/link verification (`src/ingestion/enrich_names.py`)

Run after `openalex.py`, this does two things for every professor with an ORCID id:

1. **Verifies the ORCID actually belongs to the attributed person**, by comparing ORCID's own `/employments` history against the professor's institution. This check is **country-based, not institution-name-based** — an early version compared institution name text and produced ~35% false positives, because a professor's real ORCID employer is very often a differently-named affiliate of their university (e.g. Aaron Roodman's ORCID employer is "SLAC National Accelerator Laboratory", not "Stanford University"). A country-level mismatch (e.g. a Seattle-attributed professor whose only ORCID employer is in Hong Kong) is a much rarer and stronger signal of a genuine wrong-person link. On mismatch, `Professor.orcid` is cleared (`clear_professor_orcid`) rather than left pointing at a stranger's profile — a missing link is better than a wrong one. This still can't catch a wrong-person link within the same country; that's a known residual limitation.
2. **Improves the name** from ORCID's `given-names`/`family-name`/`credit-name` (more reliable than OpenAlex's alternatives for filling gaps `prefer_full_name` couldn't, e.g. "A. M. Litke" → "Alan M. Litke"). `is_safe_replacement()` guards against regressions (never trade a fuller name for one with more bare-initial tokens, require matching surname + given-name first letter). `normalize_casing()` fixes ALL-CAPS/all-lowercase ORCID fields (e.g. "ANNA"/"GOUSSIOU" → "Anna"/"Goussiou") per-token rather than rejecting the whole candidate over formatting.

### Publications (`src/ingestion/publications.py`)

Run after professors are ingested (and ideally after `enrich_names.py`, though independent of it). For each `Professor` row with an `openalex_id`, fetches that professor's own top-cited works directly — `pyalex.Works().filter(author={"id": openalex_author_id})` — and links them via `ProfessorPublication`. This is the safe pattern the original pipeline didn't use: a publication is only ever linked to the professor whose own author id was queried for it, so there's no attribution risk the way there was with institution-level Works queries. `strip_markup()` cleans OpenAlex titles that embed raw MathML for equations (common in physics papers) so they render as plain text.

## Running things

There is no build, lint, or test framework configured yet (no pytest/test directory, no linter config). To run a script, use the module path from the repo root so intra-package imports resolve, e.g.:

```
python -m src.ingestion.openalex
python -m src.ingestion.enrich_names
python -m src.ingestion.publications
```

`src/test_connection.py` is a manual smoke-test script (imports `database` directly, not `src.database` — must be run from inside `src/`), not an automated test.

## Web app (search MVP)

- `backend/main.py` is a FastAPI app exposing `/api/search` (filter by `q`, `institution`, `city`, `state`, `country`, paginated via `page`/`limit`), `/api/professors/{id}/publications`, and `/api/institutions` (autocomplete), searching `Professor` joined to `Institution`. It reuses `src/database.py::get_connection()` directly — no ORM, no separate connection pool.
- The same app mounts `frontend/` as static files at `/`, so the API and UI are served from one process on one origin (no CORS setup needed). `frontend/index.html` + `app.js` + `style.css` is a dependency-free SPA: a filter form calls `/api/search` via `fetch` and renders professor cards (name, institution, location, email/website/ORCID if present); each card has a "Show publications" toggle that lazy-loads `/api/professors/{id}/publications` on first click.
- Run it from the repo root: `uvicorn backend.main:app --reload`, then open `http://localhost:8000/`.
- No LLM calls happen anywhere in this path yet. When adding LLM-based summaries/cold-email generation, add a new `/api/*` endpoint in `backend/main.py` rather than changing the search endpoints, and keep it opt-in from the frontend so the MVP search flow has no external API dependency or added latency.
