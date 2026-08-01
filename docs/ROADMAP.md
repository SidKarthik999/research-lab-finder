# Research Lab Finder — Roadmap

**Last updated:** 2026-08-01

## The goal

A tool that high school and university students use to find research
opportunities — in the fields they care about, at institutions and in
locations they can actually reach. The job isn't "browse a database of
academics"; it's "get a student from *I'm interested in X* to *I have sent a
credible email to a specific person who might say yes*."

Every phase below is judged against that end-to-end path.

## Where things stand (measured 2026-08-01)

| Table | Rows | Notes |
|---|---|---|
| `Institution` | 100 | all US, top 100 by OpenAlex works count |
| `Professor` | 4,431 | ~top 50 per institution by works count |
| `Publication` | 34,069 | 23,250 have abstracts |
| `ProfessorPublication` | 43,880 | safely attributed (per-author queries) |
| `Lab` | 45 | hand-extracted pilot; Stanford + Cornell only |
| `ProfessorLab` | 37 | |

Professor contact coverage: **0 emails, 0 websites**, 3,621 ORCIDs.

### What's working

The attribution rebuild did its job. Professors come from
`Authors().filter(last_known_institutions=...)` — OpenAlex answering "who
works here" directly — and publications hang off each professor's own author
id. Neither reconstructs affiliation from Works authorships, which is what
produced the misattributed labs in the first iteration. `enrich_names.py`'s
country-based ORCID verification is a sound compromise: it catches the strong
signal (wrong country) without the ~35% false-positive rate that
institution-name matching produced.

That foundation is trustworthy. The gaps below are about *reach*, not
correctness.

### What blocks the goal

1. **Search doesn't cover research fields.** `/api/search?q=` matches only
   `Professor.name` and `Institution.name`. A student searching "neuroscience"
   or "CRISPR" gets zero results. This is the single largest gap between the
   current tool and the stated goal.
2. **Nobody is contactable.** 0 of 4,431 professors have an email or a
   website. Even a perfect search result dead-ends.
3. **Coverage is the wrong slice.** Top-100 institutions × top-50 most-cited
   faculty is elite- and medicine-skewed — close to the *least* accessible
   population for an unknown student.
4. **Labs don't scale.** 45 rows from two hand-pasted directory pages.
5. **No opportunity signal.** Nothing records whether a PI or program actually
   takes students, which is the fact a student most needs.

---

## Phase 0 — Stop the schema from being a footgun

Do this before Phase 1 touches the database.

`database/schema.sql` opens with `DROP TABLE ... CASCADE` on `Professor` and
`Institution`. That was harmless at zero rows. It is now a single stray
`psql -f` away from destroying 34,069 publications that cost real API time to
collect, with no backup step in between.

- Replace `schema.sql` with numbered, additive migration files
  (`database/migrations/001_*.sql`, …) applied in order. No tooling needed —
  a `schema_migrations` table and a short runner script is enough.
- Keep the current `schema.sql` as `database/schema_full.sql` for reference /
  fresh installs only, clearly marked destructive.
- Add a `make backup` (or equivalent) `pg_dump` step, since
  `database/backups/` is already gitignored and in use.

Alongside it, add a small `pytest` suite over the pure functions that have
already caused bugs and are trivially testable in isolation:
`prefer_full_name`, `is_safe_replacement`, `normalize_casing`,
`match_professor`, `reconstruct_abstract`, `strip_markup`. No database, no
network — just the string logic where the subtle failures live.

---

## Phase 1 — Make search about research fields

The highest-value work, and it requires no new attribution logic.

**Topics.** OpenAlex `Authors` records carry a `topics` array with a
`subfield`/`field`/`domain` hierarchy and per-topic scores, derived from that
author's own works. This is the same safe pattern already in use — the data
comes from the author record, not from reconstructing affiliation.

- Reintroduce `ResearchTopic` (id, openalex_id, name, subfield, field, domain)
  and `ProfessorTopic(professor_id, topic_id, score)`.
- Populate in one `Authors` pass over the existing 4,431 professors. No
  re-ingestion, no attribution risk.
- Follow the established ingestion shape: a `get_*` fetch function, an
  `insert_openalex_*` mapper, a bulk driver with per-item try/except.

**Full-text search over abstracts.** 23,250 abstracts are already stored and
entirely unused. Topic labels are coarse; free text catches the specific term
a student actually types ("optogenetics", "perovskite").

- Add a `tsvector` column + GIN index over `Publication.title || abstract`.
- Consider a materialized view aggregating each professor's publication text,
  refreshed on ingest, so professor-level search is one indexed lookup.

**Surface it.**

- `/api/search` gains `topic` and `field` parameters.
- Replace `ORDER BY Professor.name` with relevance ranking (topic score, then
  text rank, then recent activity). The current ordering is arbitrary and
  makes results feel random.
- Frontend: topic chips on professor cards; topic autocomplete alongside the
  existing institution autocomplete.

**Done when** a student can type "computational neuroscience" + "Texas" and
get a ranked, plausible list.

---

## Phase 2 — Contactability

Zero emails means the funnel dead-ends at the moment of highest intent.

**Do not scrape or guess emails.** Directory scraping is already known to be
fragile here (every `umich.edu` subdomain returned 403 during the labs pilot),
and a guessed address that bounces — or reaches the wrong person — costs more
trust than a missing one. Same principle as clearing a mismatched ORCID:
absent beats wrong.

Instead:

- **ORCID `researcher-urls`.** The `/person` endpoint exposes researcher-
  supplied links (personal site, lab page). Reuse the OAuth client already
  built in `enrich_names.py`. Fills a real share of the 3,621 ORCID holders
  with zero scraping.
- **Contact panel per professor**, assembled from what's known: ORCID profile
  link, personal/lab site, Google Scholar deep link, and a constructed
  institution-directory search URL built from `Institution.website` + the
  professor's name. That reliably gets a student *to* a contact page even
  where the address itself isn't stored.
- **Later, optional:** per-institution directory adapters for the subset of
  schools that permit automated access, robots.txt-respecting, sharing one
  `directory.py` interface. Worth it only if Phase 5 shows outreach is the
  actual bottleneck.

---

## Phase 3 — Coverage that matches the users

The current slice is the opposite of what an unknown student needs. A high
schooler in Nebraska is not getting a lab spot from a top-50-cited Stanford
PI; they are getting one from a regional state school twenty minutes away.

- Widen ingestion beyond the top 100: all US `type=education` institutions
  above a modest works threshold. Include masters- and bachelors-granting
  institutions, not just R1s.
- Lower the per-institution professor cap so coverage broadens rather than
  deepening on the already-famous.
- Add recency: store `last_publication_year` and filter to professors with a
  work in roughly the last three years, so students don't email retired or
  inactive PIs.
- Add `Institution.type` / carnegie-style classification if available, so the
  UI can offer "schools near me" rather than only "top schools".
- The API already accepts a `country` filter — non-US expansion is a config
  change once the US set is solid, not a rebuild.

---

## Phase 4 — Labs, automated

`src/ingestion/labs.py` already has the right *structure*: surname +
first-initial matching scoped per institution, stub `Professor` creation for
unmatched PIs, `source="Lab Directory"` provenance. What it lacks is a feed —
the 45 rows were pasted in by hand.

- Seed a per-institution list of department/lab-directory URLs.
- Fetch with a robots.txt check and a polite rate limit; accept that some
  domains will refuse and record that rather than retrying blindly.
- Extract lab name / PI / URL / short blurb from the fetched HTML via an LLM
  pass — this is the part that genuinely resists a fixed parser, since no two
  directory pages share a structure.
- Feed results through the **existing** insert/match/stub path unchanged.

Guardrails: never create a stub professor without an institution and a
`source`; never source labs from OpenAlex Works (OpenAlex has no lab entity,
and Works-derived labs are exactly what was rolled back).

---

## Phase 5 — The differentiator: opportunities and outreach

Everything above builds a good directory. This is what makes it a *tool*.

**Consider promoting this above Phase 4.** High school students overwhelmingly
get research through structured programs — REUs, summer institutes, formal
mentorship schemes — not cold emails to R1 PIs. For that half of the audience,
the opportunity layer matters more than lab coverage does.

- **`Opportunity` table**: NSF REU sites, institution summer research
  programs, department-level undergraduate research listings. Fields for
  eligibility (high school / undergrad), deadline, location, paid/unpaid,
  and a link. This is the data students most need and that no OpenAlex-derived
  directory can provide.
- **Student profile**: interests, level, location radius → ranked matches
  across both professors and opportunities.
- **`/api/professors/{id}/summary`** — a plain-language "what this lab works
  on," generated from the professor's top publication abstracts. **Cache it in
  a column**, generated once at ingest time, not per request: it's stable
  data, and per-request generation would put an external API in the hot path.
- **`/api/professors/{id}/cold-email`** — a draft grounded in the student's
  profile and the professor's *recent* work, so it reads as specific rather
  than mass-mailed.

Per `CLAUDE.md`: both are new `/api/*` endpoints, and both stay opt-in from
the frontend so the core search flow keeps zero external dependencies and no
added latency.

---

## Phase 6 — Productization

- Deploy: managed Postgres + a single container serving the FastAPI app and
  static frontend (the current single-origin setup already makes this simple).
- Scheduled refresh of the ingestion pipeline, with per-stage logging so a
  partial failure is visible rather than silent.
- Saved searches and "email me new matches in my field near me" — the feature
  that makes students return rather than visit once.

---

## Suggested order

1. **Phase 0** — before anything else touches the schema.
2. **Phase 1** — largest gap, lowest risk, no new attribution logic.
3. **Phase 2** — otherwise Phase 1's better results still dead-end.
4. **Phase 3** — broadens reach once the core loop works end to end.
5. **Phase 5 before Phase 4**, if the high school audience is a priority.

## Principles carried forward

- **Attribution comes from author records, never reconstructed from Works
  authorships.** This is the mistake that forced the first rebuild.
- **Absent beats wrong.** A missing ORCID, email, or lab link is recoverable;
  a confidently wrong one costs user trust and is hard to detect.
- **Verify on a small batch before running the full set** — the 8-institution
  check before the 100-institution run is the right pattern for every new
  ingestion stage.
- **Bulk ingestion uses per-item try/except** so one bad record never aborts a
  batch.
