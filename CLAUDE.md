# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project overview

Research Lab Finder is an early-stage platform for discovering academic research labs by research interest, location, institution, and publications. Data is sourced from OpenAlex and stored in PostgreSQL. `backend/` holds a FastAPI search API and `frontend/` a plain HTML/CSS/JS SPA that consumes it; `docs/` holds `ROADMAP.md`, the phased plan this project is being built against. No LLM functionality is wired in yet — search is pure SQL filtering.

**Current state**: the schema and ingestion pipeline cover `Institution`, `Professor`, `Publication`, and (as of Phase 1, 2026-08-02) `ResearchTopic`. `Lab`, `Department`, and some junction tables were dropped (2026-08-01) after the original Works-based ingestion produced widespread misattribution (co-authors on a work got tagged with that work's institution even when they belonged elsewhere) and a pile of synthetic/junk `Lab` rows; `Lab` itself came back the same day, sourced from lab-directory pages rather than Works (see `src/ingestion/labs.py`). `Department` is still shelved. See docs/ROADMAP.md for what's done and what's next, and "Ingestion pipeline" below for the corrected attribution method — don't reintroduce the Works-based approach when touching any of this.

Future goals (from docs/ROADMAP.md): contactability (Phase 2), broader institution coverage (Phase 3), automated lab ingestion (Phase 4), and an opportunities/outreach layer with LLM-based summaries and cold-email generation (Phase 5). The backend is intentionally structured so an `/api/*` endpoint calling an LLM can be added later without touching the search path.

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
- Core entity tables: `Institution`, `Professor` (`Professor.institution_id` → `Institution.id`), `Publication`, joined by `ProfessorPublication`. Location fields (`city`, `state`, `country_code`) live on `Institution`, not `Professor` — a professor's location is their institution's location. `ResearchTopic` (name/subfield/field/domain, from OpenAlex's topic taxonomy) is joined to `Professor` via `ProfessorTopic(professor_id, topic_id, works_count)` — `works_count` is OpenAlex's per-topic work count for that author, used as a relevance signal since Author.topics has no separate normalized score.
- `Publication.search_vector` is a `GENERATED ALWAYS AS ... STORED` `tsvector` column (title weighted 'A', abstract weighted 'B') with a GIN index, added in migration `003_publication_search_vector.sql`. It stays in sync automatically on insert/update — nothing in the ingestion code needs to maintain it.
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

### ORCID client (`src/ingestion/orcid_client.py`)

Shared OAuth client-credentials token handling, request throttling/retry (0.1s between requests with API credentials configured, 1s without, backing off on 429s), and the authenticated GET helper for ORCID's public API. Both `enrich_names.py` and `researcher_urls.py` import this rather than each keeping their own copy — this used to be duplicated inline in `enrich_names.py` until `researcher_urls.py` needed the same thing.

### ORCID-based name/link verification (`src/ingestion/enrich_names.py`)

Run after `openalex.py`, this does two things for every professor with an ORCID id:

1. **Verifies the ORCID actually belongs to the attributed person**, by comparing ORCID's own `/employments` history against the professor's institution. This check is **country-based, not institution-name-based** — an early version compared institution name text and produced ~35% false positives, because a professor's real ORCID employer is very often a differently-named affiliate of their university (e.g. Aaron Roodman's ORCID employer is "SLAC National Accelerator Laboratory", not "Stanford University"). A country-level mismatch (e.g. a Seattle-attributed professor whose only ORCID employer is in Hong Kong) is a much rarer and stronger signal of a genuine wrong-person link. On mismatch, `Professor.orcid` is cleared (`clear_professor_orcid`) rather than left pointing at a stranger's profile — a missing link is better than a wrong one. This still can't catch a wrong-person link within the same country; that's a known residual limitation.
2. **Improves the name** from ORCID's `given-names`/`family-name`/`credit-name` (more reliable than OpenAlex's alternatives for filling gaps `prefer_full_name` couldn't, e.g. "A. M. Litke" → "Alan M. Litke"). `is_safe_replacement()` guards against regressions (never trade a fuller name for one with more bare-initial tokens, require matching surname + given-name first letter). `normalize_casing()` fixes ALL-CAPS/all-lowercase ORCID fields (e.g. "ANNA"/"GOUSSIOU" → "Anna"/"Goussiou") per-token rather than rejecting the whole candidate over formatting.

### Professor websites (`src/ingestion/researcher_urls.py`, Phase 2)

Run after `enrich_names.py` (not required, but avoids fetching researcher-urls for an ORCID id that gets cleared as a wrong-person match). For every professor with an ORCID id, fetches ORCID's `/researcher-urls` — links the researcher themselves added to their public profile — and backfills `Professor.website` with the best one found. No scraping, no guessing: every URL came from the researcher's own ORCID record.

Most professors have zero researcher-urls on file (in a spot-check of 60, only 5 had any) — that's expected, not a bug. `pick_best_researcher_url()` is a pure function that: excludes social/networking links (LinkedIn, Twitter, etc. — matched against the free-text `url-name` ORCID users typed themselves, so best-effort not exhaustive), prefers a URL whose name signals an actual personal/lab/faculty page ("lab", "faculty", "homepage", ...), and otherwise falls back to the first remaining candidate (e.g. Google Scholar, a publications list) rather than returning nothing. Real ORCID data has entries with a blank `url-name` that are still legitimate lab sites (e.g. `gmwgroup.harvard.edu` with no name at all) — those still count as fallback candidates.

### Publications (`src/ingestion/publications.py`)

Run after professors are ingested (and ideally after `enrich_names.py`, though independent of it). For each `Professor` row with an `openalex_id`, fetches that professor's own top-cited works directly — `pyalex.Works().filter(author={"id": openalex_author_id})` — and links them via `ProfessorPublication`. This is the safe pattern the original pipeline didn't use: a publication is only ever linked to the professor whose own author id was queried for it, so there's no attribution risk the way there was with institution-level Works queries. `strip_markup()` cleans OpenAlex titles that embed raw MathML for equations (common in physics papers) so they render as plain text.

### Research topics (`src/ingestion/topics.py`)

Run after professors are ingested (independent of `enrich_names.py`/`publications.py`). For each `Professor` row with an `openalex_id`, fetches that professor's own OpenAlex Author record and reads its `topics` field directly (`pyalex.Authors()[openalex_author_id]`), rather than inferring subject matter from Works affiliated with an institution — the same safe per-author pattern `publications.py` uses. Each topic in `Author.topics` is derived from that author's own works, so there's no attribution risk. Author.topics has no normalized score field; each topic instead carries a `count` (how many of the author's own works are tagged with it, already ordered most-relevant-first), stored as `ProfessorTopic.works_count`.

## Running things

There is no build or linter configured yet. To run a script, use the module path from the repo root so intra-package imports resolve, e.g.:

```
python -m src.ingestion.openalex
python -m src.ingestion.enrich_names
python -m src.ingestion.publications
python -m src.ingestion.topics
python -m src.ingestion.researcher_urls
```

`src/test_connection.py` is a manual smoke-test script (imports `database` directly, not `src.database` — must be run from inside `src/`), not an automated test.

A `pytest` suite lives in `tests/`, covering the pure logic where the subtle bugs have historically been: `prefer_full_name`, `is_safe_replacement`, `normalize_casing` (name quality), `match_professor` (lab-PI matching), `reconstruct_abstract`, `strip_markup` (publication text), and `build_search_query` (backend/main.py's `/api/search` SQL builder — the risk there is placeholder/param misalignment across several optional filters, not string logic, but the same "no DB, fast, exhaustive" testing approach applies). No database or network access — run with `python -m pytest` (or `make test`) from the repo root. `pytest.ini` scopes collection to `tests/` so `src/test_connection.py` isn't picked up as a test. When adding a new pure function with the same "subtle bug" shape, add coverage here rather than only exercising it via a manual `__main__` run.

## Web app (search MVP)

- `backend/main.py` is a FastAPI app exposing `/api/search` (filter by `name`, `text`, `institution`, `city`, `state`, `country`, `topic`, `field`, paginated via `page`/`limit`), `/api/professors/{id}/publications`, `/api/institutions` (autocomplete), `/api/topics` (autocomplete), and `/api/fields`, searching `Professor` joined to `Institution` and (as of Phase 1) `ProfessorTopic`/`ResearchTopic`/`Publication.search_vector`. It reuses `src/database.py::get_connection()` directly — no ORM, no separate connection pool.
- `/api/search`'s SQL/param assembly lives in `build_search_query()`, kept separate from the route handler so it's testable without a DB connection (see `tests/test_search_query.py`). All filters are strict/AND'd. There used to be a single combined `q` "keyword" param that silently OR'd professor-name, institution-name, topic, and publication full-text matching together — once `institution`/`topic`/`field` got their own dedicated filters that became redundant duplication with an unclear name, so it was split into `name` (professor's own name — the one thing no other filter covers) and `text` (free-text search over publication titles/abstracts, finer-grained than the curated topic taxonomy — the other thing no other filter covers). `topic` matches ResearchTopic's `name`, `field`, *and* `subfield` (not just `name`) since OpenAlex rarely has a topic literally named e.g. "Computer Science" — that only exists as a `field` value, with ~176 specific topics under it; matching all three levels lets a broad term catch everything beneath it. Results are ranked by topic relevance (OpenAlex's per-topic `works_count` for whatever matched via `topic`/`field`), then `text`'s full-text rank, then most recent publication date — replacing the old arbitrary `ORDER BY Professor.name`. Each result also carries up to 3 `topics` (chip labels), with whichever topic matched `topic`/`field` always shown first rather than just the professor's single largest topic.
- `/api/fields` returns all distinct `ResearchTopic.field` values unfiltered/unpaginated (~26 of them, OpenAlex's fixed top-level taxonomy) — unlike `/api/topics`/`/api/institutions` (thousands of values, need `q`/`limit`), the frontend just renders the whole list as a `<select>` dropdown rather than an autocomplete-as-you-type box.
- `/api/topics` also takes an optional `field` param (exact match, since values come from the `/api/fields` dropdown) to scope suggestions to that field — e.g. `field=Neuroscience` only suggests topic names that actually fall under Neuroscience. The frontend puts the Field `<select>` before the Research topic box in the form for this reason: pick the broad area first, then get narrower, already-scoped suggestions as you type.
- The same app mounts `frontend/` as static files at `/`, so the API and UI are served from one process on one origin (no CORS setup needed). `frontend/index.html` + `app.js` + `style.css` is a dependency-free SPA. The main form has Field (`<select>`, from `/api/fields`), Research topic (autocomplete against `/api/topics`, re-scoped to the selected field on `change`), and Institution (autocomplete against `/api/institutions`). A collapsed `<details id="advanced-search">` holds the less-common filters: Professor name (`name`), Search publications (`text`, with a hint clarifying it searches actual paper text, not topic categories), and City/State/Country — kept out of the primary form since most searches won't need them, but still real `<input>`s inside the `<form>` so `FormData` in `app.js` picks them up whether the `<details>` is expanded or not. It calls `/api/search` via `fetch` and renders professor cards (name, institution, location, topic chips).
- **Contact panel (Phase 2)**: each card's contact line combines stored data (email, `Professor.website` — backfilled by `researcher_urls.py`, ORCID) with two links computed client-side from data already in the `/api/search` response, no extra request or storage: a Google Scholar author-search link (`scholarSearchUrl()`), and an institution-directory search link (`directorySearchUrl()`, `site:<institution domain> <professor name>` via Google, domain extracted from the now-returned `institution_website` field). Deliberately search links, not scraped/guessed direct URLs — same "absent/searchable beats wrong" principle as the ORCID work, and it reliably gets a student *to* a place to look even without a stored URL. Each card also has a "Show publications" toggle that lazy-loads `/api/professors/{id}/publications` on first click.
- Run it from the repo root: `uvicorn backend.main:app --reload`, then open `http://localhost:8000/`.
- No LLM calls happen anywhere in this path yet. When adding LLM-based summaries/cold-email generation, add a new `/api/*` endpoint in `backend/main.py` rather than changing the search endpoints, and keep it opt-in from the frontend so the MVP search flow has no external API dependency or added latency.
