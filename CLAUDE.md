# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project overview

Research Lab Finder is an early-stage platform for discovering academic research labs by research interest, location, institution, and publications. Data is sourced from OpenAlex and stored in PostgreSQL. `backend/`, `frontend/`, and `docs/` are placeholder directories with no content yet — the project currently consists of a Python ingestion pipeline and a database schema. Do not assume a web app or API exists yet.

Future goals (from README, not yet built): automated lab/publication ingestion beyond institutions and professors, a search backend, and LLM-based lab summaries / cold-email generation.

## Environment setup

The project uses a conda environment defined in `environment.yml`:

```
conda env create -f environment.yml
conda activate researchlabfinder
```

Dependencies are pinned via conda + pip (`pyalex`, `python-dotenv`, `psycopg`). There is no `requirements.txt` — `environment.yml` is the source of truth.

Secrets (e.g. `OPENALEX_API_KEY`) live in a local `.env` file, loaded via `python-dotenv`. `.env` is gitignored — never commit it.

## Database

- PostgreSQL database name: `research_lab_finder`. Connection is hardcoded in `src/database.py::get_connection()` (dbname + local user, no host/password — assumes a local Postgres instance with peer/trust auth).
- Schema lives in `database/schema.sql`, seed data in `database/seed.sql`, ad-hoc queries in `database/queries.sql`. There is no migration tool — schema changes are applied by hand (e.g. `psql -d research_lab_finder -f database/schema.sql`).
- Core entity tables: `Institution`, `Department`, `Professor`, `Lab`, `Publication`, `ResearchTopic`, joined by junction tables (`ProfessorPublication`, `PublicationTopic`, `LabResearchTopic`, `ProfessorDepartment`, `ProfessorLab`).
- Rows carry a `source` column (e.g. `"OpenAlex"`, `"manual"`) plus `created_at`/`updated_at`, to distinguish ingested vs. hand-seeded data.
- Upserts follow a consistent pattern: `INSERT ... ON CONFLICT (<unique_key>) DO UPDATE SET updated_at = CURRENT_TIMESTAMP RETURNING id`, keyed off natural unique identifiers (`openalex_id`, `ror_id`, or a `(name, institution_id)` pair). Follow this pattern for any new insert function in `src/database.py`.

## Ingestion pipeline

`src/ingestion/openalex.py` wraps the `pyalex` client to pull data from OpenAlex and insert it via `src/database.py`:

- `search_institution(name)` — looks up a single institution by name via OpenAlex search.
- `insert_openalex_institution(name)` / `insert_institutions_from_file(filename)` — insert one or many institutions (one name per line, see `data/institutions.txt`); failures per-line are caught and logged, not fatal.
- `get_openalex_works(institution_name)` — fetches works (papers) affiliated with an institution.
- `insert_openalex_professor(author)` / `insert_professors_from_institution(name)` — derives professors from the authorships of an institution's works, rather than a dedicated OpenAlex authors query.

When adding a new ingestion entity (e.g. labs, publications, topics), mirror this shape: a `search_*`/`get_*` fetch function, an `insert_openalex_*` mapper that translates the OpenAlex JSON shape into the `insert_*` call in `src/database.py`, and (if bulk) an `insert_*_from_*` driver with per-item try/except so one bad record doesn't abort the batch.

Scripts are run directly (`if __name__ == "__main__":` blocks double as manual test harnesses) — there is no CLI framework or task runner yet.

## Running things

There is no build, lint, or test framework configured yet (no pytest/test directory, no linter config). To run a script, use the module path from the repo root so intra-package imports resolve, e.g.:

```
python -m src.ingestion.openalex
```

`src/test_connection.py` is a manual smoke-test script (imports `database` directly, not `src.database` — must be run from inside `src/`), not an automated test.
