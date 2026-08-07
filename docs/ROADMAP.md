# Research Lab Finder — Roadmap

**Last updated:** 2026-08-06

> **Next up: Phase 5A** (professor profiles, AI summaries, cold emails, and
> Google sign-in). Promoted ahead of Phases 3 and 4 on 2026-08-06 — see
> "Suggested order" for why. Phase numbers are deliberately *not* renumbered:
> several code comments (`src/ingestion/openalex.py`, migration headers)
> already cite phase numbers, and silently shifting them would make those
> comments point at the wrong thing.

## The goal

A tool that high school and university students use to find research
opportunities — in the fields they care about, at institutions and in
locations they can actually reach. The job isn't "browse a database of
academics"; it's "get a student from *I'm interested in X* to *I have sent a
credible email to a specific person who might say yes*."

Every phase below is judged against that end-to-end path.

## Where things stand (measured 2026-08-02, mid-Phase 2)

| Table | Rows | Notes |
|---|---|---|
| `Institution` | 100 | all US, top 100 by OpenAlex works count |
| `Professor` | 4,431 | ~top 50 per institution by works count |
| `Publication` | 34,069 | 23,250 have abstracts, all with a full-text `search_vector` |
| `ProfessorPublication` | 43,880 | safely attributed (per-author queries) |
| `ResearchTopic` | 2,483 | from each professor's own OpenAlex Author.topics |
| `ProfessorTopic` | 21,864 | across 4,377 professors (54 had zero topics from OpenAlex) |
| `Lab` | 45 | hand-extracted pilot; Stanford + Cornell only |
| `ProfessorLab` | 37 | |

**Phase 1 is done**: `/api/search` now has `topic`/`field` filters, free-text search over topics and publication full text (split into `name`/`text`/`topic`/`field`, replacing an earlier combined `q` that turned out to conflate several unrelated things — see commit history), and relevance ranking (topic match, then text rank, then recency) in place of the old alphabetical order. Frontend has topic chips, a Field dropdown, field-scoped topic autocomplete, and an Advanced search section. 137 new tests (309 total).

One honest caveat from Phase 1: the phase's own "done when" example (`computational neuroscience` + `Texas`) currently returns zero results — not a search bug, but a coverage gap. Only 4 of the 100 ingested institutions are in Texas, and "computational neuroscience" as an exact phrase doesn't overlap with any of their professors' topics/abstracts. Broader combinations (e.g. `neuroscience` + `California`, which has many more ingested institutions) work as intended. This is precisely the gap Phase 3 (coverage) exists to close.

**Phase 2 is done**: `researcher_urls.py` backfilled `Professor.website` from ORCID's researcher-urls (653 of 3,621 ORCID holders had a usable one — most people don't add any). `emails.py` backfilled `Professor.email` from ORCID's public, ORCID-verified `emails` field (293 of 3,621 — only ~8% make an email public, but every one is opt-in-disclosed and verified, not scraped or guessed). The frontend contact panel also shows a Google Scholar author-search link and an institution site-search link, both computed on the fly from data already on hand — link wording and the Scholar query were both tuned after real usage turned up problems (see commit history: appending institution to the Scholar query regressed a real profile and was reverted; the directory link was relabeled since it's a search, not an actual directory).

Professor contact coverage: **293 emails, 653 websites** (up from 0/0), 3,621 ORCIDs.

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

1. ~~**Search doesn't cover research fields.**~~ **Fixed in Phase 1.**
   `/api/search` now filters by topic/field and full-text publication search.
2. ~~**Nobody is contactable.**~~ **Fixed in Phase 2**, as much as it's going
   to be without scraping. 653 of 4,431 professors have a website, 293 have a
   verified public email (both from ORCID, nothing scraped or guessed), and
   every result has computed Scholar/institution search links regardless.
   Most professors still won't have a direct email — that's a real ceiling
   of "what's legitimately public," not a to-do item.
3. **Finding the right person isn't the same as being able to approach
   them.** A result card is a name, an institution, and three topic chips.
   A student who lands on the right professor still has to work out who they
   are, whether their work is actually a fit, and what to say — which is the
   step most of them stall on. This is what Phase 5A addresses, and it's now
   the top of the critical path.
4. **Coverage is the wrong slice.** Top-100 institutions × top-50 most-cited
   faculty is elite- and medicine-skewed — close to the *least* accessible
   population for an unknown student.
5. **Labs don't scale.** 45 rows from two hand-pasted directory pages.
6. **No opportunity signal.** Nothing records whether a PI or program actually
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
  `directory.py` interface. Worth it only if Phase 5A shows outreach is the
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

## Phase 5A — Profiles, AI summaries, and cold emails ← **next up**

Everything above builds a good directory. This is what makes it a *tool*, and
it's the shortest remaining path to the goal stated at the top: *I have sent a
credible email to a specific person who might say yes.* Phases 3 and 4 make
the directory bigger; this one makes it act.

**Professor detail view.** Today a professor is a card in a result list.
Give each one a real page — reachable by clicking the card, with its own URL
so it can be bookmarked and shared — showing institution and location, the
full topic list (not just 3 chips), the contact panel, and their publications
without a separate "show" click.

**`/api/professors/{id}/summary`** — a plain-language paragraph on who this
person is and what they work on, generated from their name, institution,
topics, and the titles/abstracts of their most-cited and most-recent papers.

- **Cache it in a column** (`Professor.ai_summary` + a generated-at
  timestamp). Generate lazily on first view rather than for all 4,431
  professors at ingest: most professors will never be viewed, the data is
  stable once written, and a per-request call would put an external API in
  the hot path of a page load.
- Ground it strictly in the rows passed in, and say plainly in the UI that
  it's AI-generated from public publication data. Same principle as
  everywhere else in this project: **absent beats wrong**, and a confident
  hallucination about a real named academic is the worst failure mode this
  product has.

**Accounts.** The cold email needs to brag about the student, which means the
student's details have to live somewhere: a `StudentProfile` filled in once
(level, school, coursework, skills/techniques, prior projects, what they're
looking for) and reused for every draft.

Auth is **multi-provider from day one** — "Continue with Google" alongside
ordinary email-and-password, and room for Apple/Microsoft/GitHub later
without a migration. That means the account and the login method are
*separate* records: one `AppUser` row, one `AuthIdentity` row per method,
so the same person signing in with Google today and a password tomorrow
lands in one account rather than two.

Two rules that are easy to get wrong and expensive to fix:

- **Link accounts only on a provider-*verified* email.** Auto-linking an
  unverified one is a known account-takeover path: an attacker registers a
  password account under someone else's address, that person later signs in
  with Google, and the two get merged into the attacker's account.
- **A student's own profile text goes into a prompt.** Treat it as untrusted
  input for prompt-injection purposes, and never let it reach an endpoint
  that acts on its own output.

**`/api/professors/{id}/cold-email`** — a draft grounded in *both* sides:
the student's profile and the professor's *recent* work specifically, so it
reads as written by someone who actually read a paper rather than
mass-mailed. Editable in the browser before it's sent; the app drafts, the
student sends.

**Frontend groundwork, done as part of 5A rather than after it.** This phase
roughly triples the frontend (detail page, sign-in, signup, profile form,
email composer, account menu). Three things are much cheaper to do while
writing those screens than to retrofit across all of them:

- **Missing style primitives.** `style.css` is already token-driven and
  handles dark mode, but it has one button style (`.publications-toggle`
  fakes a secondary by overriding `background`), no `textarea`, no error or
  success styling, and no header bar with room for account state. Add a
  spacing/type scale and those primitives up front, or five screens each
  invent their own and drift. This is *not* the redesign — see Phase 5C.
- **An `el(tag, attrs, ...children)` DOM helper** replacing the
  `innerHTML` + template-literal + hand-called `escapeHtml()` pattern.
  That pattern is correct today only because every interpolation
  remembered to escape; 5A introduces genuinely user-controlled strings
  (display names, profile text, model output) where today nearly
  everything comes from OpenAlex. Building nodes with `textContent`
  removes the whole class of bug instead of reducing it.
- **Split `app.js` into ES modules** (`api.js`, `session.js`, `router.js`,
  `views/`) using native `<script type="module">`. 255 lines is fine; ~800
  with six views and auth state is not.

**Done when** a signed-in student can go from a search result to a specific
professor's page, read a summary that's accurate, and copy out an email that
names a real paper and a real reason they're a fit.

Per `CLAUDE.md`: these are new `/api/*` endpoints, and they stay opt-in from
the frontend so the core search flow keeps zero external dependencies and no
added latency for signed-out users.

---

## Phase 5B — Opportunities

The other half of the original Phase 5, still worth doing but not blocking
5A. High school students overwhelmingly get research through structured
programs — REUs, summer institutes, formal mentorship schemes — not cold
emails to R1 PIs. For that half of the audience, this layer matters more than
lab coverage does.

- **`Opportunity` table**: NSF REU sites, institution summer research
  programs, department-level undergraduate research listings. Fields for
  eligibility (high school / undergrad), deadline, location, paid/unpaid,
  and a link. This is the data students most need and that no OpenAlex-derived
  directory can provide.
- **Ranked matches** across both professors and opportunities, using the
  `StudentProfile` that Phase 5A already introduces — interests, level,
  location radius.

---

## Phase 5C — Visual redesign

Not a priority, and deliberately scheduled **after** 5A rather than before or
during it. The reasoning, so this doesn't get relitigated:

- 5A roughly triples the number of screens. Art-directing three screens now
  means redoing it once the other five exist and don't fit the system.
- The markup lives in template literals inside `app.js`. A redesign that
  changes structure means editing those; doing it once, after every screen
  exists, is the entire saving.
- `style.css` isn't a mess to escape from — 186 lines, custom properties,
  dark mode, bare-element selectors that new markup inherits from for free.
  There's no cleanup pressure forcing the issue early.

The primitives (spacing/type scale, button variants, form and error styles,
header bar) land in 5A because five screens need them regardless. 5C is the
identity work on top: typography with actual personality, colour beyond one
accent blue, result-card and detail-page art direction, landing page.

**Stay vanilla — no framework, and don't bundle that decision into the
redesign.** Restyling and re-architecting simultaneously means a breakage
can't be attributed to either one.

- A build step is the real cost. Today `uvicorn backend.main:app` serves API
  and UI from one process on one origin with no `node_modules` and no
  bundler, and Phase 6 assumes exactly that ("a single container serving the
  FastAPI app and static frontend"). A bundler makes that plan meaningfully
  harder for a frontend measured in hundreds of lines.
- **The switch signal is not line count.** It's manually re-rendering the
  same DOM from three different places and getting stale-UI bugs — the
  header still reads "Sign in" after login, the profile form shows stale
  values. That's when hand-rolled state stops being cheaper than a
  framework.
- **If that happens**, vendor Preact + htm as a single ES module file into
  `frontend/` — components and real diffing, still no build step, still one
  process. The 5A module split is what makes that an incremental migration
  rather than a rewrite, which is why it's worth doing now.

---

## Phase 6 — Ship it

Everything above assumes `localhost`. This phase is what stands between that
and a URL a student can open. The architecture is already close — one process
serving API and UI on one origin — so most of the work is configuration,
guardrails, and a handful of specific code changes that only matter once the
database is somewhere else.

### 6.1 — Code changes that block deployment

These are prerequisites, not polish. Nothing can deploy until they're done.

- **`get_connection()` cannot reach a remote database.** It hardcodes
  `dbname` and `user` with no host, port, or password, relying on local
  peer/trust auth. Replace with a `DATABASE_URL` env var (falling back to
  today's local values so nothing breaks in development).
- **Connection handling won't survive a managed instance.** The current
  function caches one connection per thread in a `threading.local` and
  reuses it forever. That's fine against local Postgres, and wrong against
  a hosted one for two reasons: FastAPI runs sync endpoints in a threadpool
  (~40 threads by default), so the app can hold ~40 permanent connections
  against a plan that may cap at 20; and managed providers drop idle
  connections, after which a cached handle can fail on next use without
  `connection.closed` having flipped. Replace with `psycopg_pool.ConnectionPool`,
  opened and closed in a FastAPI lifespan handler, with a bounded size and
  liveness check on checkout.
- **Secrets come from the environment, not a file.** `.env` + `python-dotenv`
  stays for local dev; production reads `DATABASE_URL`, `OPENAI_API_KEY`,
  `SESSION_SECRET`, `GOOGLE_CLIENT_ID`, and the email-provider key from the
  platform's secret store. Fail loudly at startup if any are missing rather
  than at first request.
- **Session cookies need production flags** — `Secure`, `HttpOnly`,
  `SameSite=Lax` — set from an `ENV`/`DEBUG` flag so local HTTP still works.
- **The migration path has never been run against an empty database.**
  `001_initial_schema.sql` was written to be a safe no-op against the
  already-live schema, which means the from-scratch case is untested. Verify
  by creating a throwaway database and running `python -m database.migrate`
  into it before trusting it as the deploy step.
- **`/healthz`** returning 200 only if a database query succeeds, so the
  platform restarts a container that's up but can't serve.

### 6.2 — Hosting shape

- **Managed Postgres** (Neon, Supabase, Render, or Fly Postgres). The dataset
  is small — ~4.4k professors, ~34k publications — so the cheapest tier is
  genuinely sufficient; this is not a scale problem. Migrate with `pg_dump`
  from local and `psql` restore into the managed instance.
- **One container** running `uvicorn backend.main:app`, serving `/api/*` and
  mounting `frontend/` at `/`. No CORS, no separate static host, no CDN
  needed at this size. Render or Fly.io both do container + managed Postgres
  with the least ceremony; a plain VPS also works and is cheaper if you don't
  mind owning TLS renewal.
- **A real domain with TLS.** Not optional: Google OAuth requires registered
  authorized origins and redirect URIs, and `Secure` cookies require HTTPS.
- **Deploy = build image → run `python -m database.migrate` as a release
  step → start the server.** Migrations run before the new code serves
  traffic, which the numbered additive-migration design already supports.
- **Automated backups**, either the provider's point-in-time recovery or a
  scheduled `pg_dump`. The publication and topic data cost real API time to
  collect and is not quickly reproducible.

### 6.3 — Where the ingestion pipeline runs

The enrichment pipeline currently runs as three launchd agents on a personal
Mac (`launchd/*.plist`), which stops working the moment the database moves.
Two options, and the cheap one is fine for a long time:

- **Keep it local, pointed at the production database** via `DATABASE_URL`.
  Zero new infrastructure, and it preserves the rate-limit circuit breakers
  and daily-resume scheduling already tuned in those plists. Downside: it
  only runs when that machine is on.
- **Move to platform cron** (Render cron jobs, Fly scheduled machines, or
  GitHub Actions on a schedule) once that becomes annoying — the scripts are
  already independent module entry points, so this is a scheduling change,
  not a rewrite.

Either way, add per-stage logging so a partial failure is visible rather than
silent.

### 6.4 — Guardrails before real users

The LLM endpoints from Phase 5A change the risk profile. Without limits, one
user or one script can spend real money on your API key.

- **Per-user daily cap on cold-email generation**, enforced server-side.
  Summaries are naturally bounded because they cache after first view; email
  drafting is not.
- **A monthly spend alert** on the OpenAI account, so a runaway loop is
  discovered by a notification rather than an invoice.
- **Rate limits on auth endpoints** (login, signup, password reset) by IP and
  by email, which the Phase 5A design already calls for.
- **Treat email drafting as a spam vector.** It generates persuasive
  messages addressed to real named academics. Requiring an account plus a
  daily cap plus keeping the send action manual (the app drafts, the student
  sends) is the mitigation — do not add a "send for me" button.

### 6.5 — Trust, and the fact that this app is about real people

Every row is a real named academic who did not sign up for this. The data is
public and properly attributed, but shipping to strangers raises obligations
that a localhost prototype doesn't have.

- **Privacy policy and terms**, covering what's stored for accounts and what
  the AI features do with a student's profile text.
- **State the data provenance on-site** — OpenAlex and ORCID, both public —
  and label AI-generated text as generated, per the principle below.
- **A working contact path for correction or removal requests** from a
  professor who asks. Small, but it's the difference between a defensible
  project and an awkward email you have no process for.

### 6.6 — Knowing when it breaks

- Error reporting (Sentry's free tier is sufficient) so failures surface
  without reading logs.
- An uptime check against `/healthz`.
- CI running `python -m pytest` on push. The suite is already meaningful and
  is worth having gate a deploy.

### 6.7 — Rough running cost

Small hosting tier plus small managed Postgres lands around **$0–25/month**
at this stage; several providers have free tiers this dataset fits inside.
The variable is LLM usage — roughly **$0.002 per professor summary** on
`gpt-5.4-nano` (down from an original ~$0.02 estimate against Claude Opus 5;
switched providers in Phase 5A once the feature was built — see CLAUDE.md),
paid once each thanks to caching, plus per-draft email cost. The caps in 6.4
are what keep that bounded.

**Done when** a student who has never met you can open a URL, search, sign
in, and get an email draft — and when you'd find out it was broken without a
user telling you.

### Later, once people actually return

- Saved searches and "email me new matches in my field near me" — the
  feature that turns a one-time visit into a returning user. Worth building
  after there's evidence people come back at all.

---

## Suggested order

1. ~~**Phase 0**~~ — done.
2. ~~**Phase 1**~~ — done.
3. ~~**Phase 2**~~ — done.
4. **Phase 5A** — *current*. Search and contactability both work now, so the
   remaining gap on the critical path isn't reach, it's that a student who
   finds the right professor still has to figure out who they are and what to
   say. Phases 3 and 4 scale a funnel that doesn't yet close; this closes it.
   It's also the cheapest test of whether the end-to-end idea works at all —
   if the generated emails aren't credible, that's worth learning before
   ingesting another 900 institutions.
5. **Phase 3** — broadens reach once the loop works end to end.
6. **Phase 5B before Phase 4**, if the high school audience is a priority.
7. **Phase 5C** — whenever. It's not on the critical path and blocks
   nothing, but it should follow 5A rather than precede it.
8. **Phase 6** — can come as early as right after 5A; it does not require
   Phase 3's wider coverage or Phase 4's labs. Shipping a narrower product
   to real users teaches more than either.

Two caveats on ordering within Phase 6. The **6.1 code changes are cheaper
during 5A than after it** — `DATABASE_URL` and the connection pool touch
`get_connection()`, which every new endpoint in 5A will call, and the cookie
flags are set where 5A creates the session. Do those two alongside 5A even if
the deploy itself waits. Everything else in Phase 6 genuinely can wait until
you're ready to ship.

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
- **Generated text is grounded in stored rows, and labeled as generated.**
  The "absent beats wrong" rule doesn't get suspended because an LLM wrote
  it. Every AI summary or email draft is built only from data already in the
  database, is shown to the user as AI-generated, and is editable before it
  goes anywhere. The app drafts; the student sends.
