# Research Lab Finder — Roadmap

**Last updated:** 2026-08-08

> **Next up: Phase 6** (shipping to real users). Phase 5A shipped in full on
> 2026-08-07/08 — profiles, AI summaries, accounts, cold-email drafting,
> bookmarking, and resume import are all live — and Phase 3's coverage
> widening + Carnegie classification landed alongside it. Phase 6.1 (pooled
> DB connections, `DATABASE_URL`, `/healthz`) is also already done. What's
> left to actually put this in front of a student is the rest of Phase 6
> (hosting, guardrails, trust/legal, monitoring) — **promoted ahead of
> Phase 4 on 2026-08-08 at the user's direction**: the app should reach other
> users before more content (labs) is added. See "Suggested order" for the
> full reasoning. Phase numbers are deliberately *not* renumbered: several
> code comments (`src/ingestion/openalex.py`, migration headers) already cite
> phase numbers, and silently shifting them would make those comments point
> at the wrong thing.

## The goal

A tool that high school and university students use to find research
opportunities — in the fields they care about, at institutions and in
locations they can actually reach. The job isn't "browse a database of
academics"; it's "get a student from *I'm interested in X* to *I have sent a
credible email to a specific person who might say yes*."

Every phase below is judged against that end-to-end path.

## Where things stand (measured 2026-08-08, end of Phase 5A / Phase 3 coverage widening)

| Table | Rows | Notes |
|---|---|---|
| `Institution` | ~1,764 | widened in Phase 3 from a fixed top-100 to every US educational institution above a works-count floor (`get_us_institutions`) |
| `Professor` | ~196,000 | widened in Phase 3 from flat top-50-by-citations to top-cited-*per-field* per institution (`get_professors_at_institution_by_field`), so coverage isn't dominated by whichever field is most-cited overall |
| `Publication` / `ProfessorTopic` / `ResearchTopic` | catching up | enrichment (topics, publications, ORCID) runs as a scheduled daily pipeline (`launchd/*.plist`) and is still working through the ~44x larger professor set; as of the recency-filter work only ~11% of professors had any `Publication` row yet — not inactivity, just enrichment lag |
| `Institution.carnegie_classification` | ~78% matched | backfilled from ACE/Indiana University's real Carnegie Classification dataset (not a heuristic), matched by name+city token-Jaccard with a bounded LLM pass for the ambiguous band; left `NULL` rather than guessed when no same-city candidate exists |
| `Lab` | 45 | unchanged since the hand-extracted pilot; Stanford + Cornell only — still the gap Phase 4 exists to close |
| `AppUser` / `AuthIdentity` / `StudentProfile` / `EmailDraft` / `Bookmark` | live | accounts, cold-email drafts, and bookmarking shipped in Phase 5A (2026-08-07/08) |

Because publication/topic enrichment is still catching up to the widened professor set, some things that depend on it (recency filtering, full-text search hit rate for newly-added institutions) are currently opt-in or partial rather than complete — see Phase 3 below.

**Phase 1 is done**: `/api/search` now has `topic`/`field` filters, free-text search over topics and publication full text (split into `name`/`text`/`topic`/`field`, replacing an earlier combined `q` that turned out to conflate several unrelated things — see commit history), and relevance ranking (topic match, then text rank, then recency) in place of the old alphabetical order. Frontend has topic chips, a Field dropdown, field-scoped topic autocomplete, and an Advanced search section. 137 new tests (309 total).

**Phase 2 is done**: `researcher_urls.py` backfilled `Professor.website` from ORCID's researcher-urls. `emails.py` backfilled `Professor.email` from ORCID's public, ORCID-verified `emails` field. The frontend contact panel also shows a Google Scholar author-search link and an institution site-search link, both computed on the fly from data already on hand — link wording and the Scholar query were both tuned after real usage turned up problems (see commit history: appending institution to the Scholar query regressed a real profile and was reverted; the directory link was relabeled since it's a search, not an actual directory).

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
   to be without scraping — website/email from ORCID (nothing scraped or
   guessed), plus computed Scholar/institution search links on every result.
   Most professors still won't have a direct email — that's a real ceiling
   of "what's legitimately public," not a to-do item.
3. ~~**Finding the right person isn't the same as being able to approach
   them.**~~ **Fixed in Phase 5A** (2026-08-07/08). Every professor now has a
   detail page with a full topic list, a cached AI summary, and a cold-email
   draft grounded in both the student's saved profile and the professor's own
   recent work. Accounts (multi-provider), bookmarking, saved/editable
   drafts, and resume-PDF profile import all shipped alongside it.
4. ~~**Coverage is the wrong slice.**~~ **Mostly fixed in Phase 3.**
   Ingestion widened from a fixed top-100 to ~1,764 US educational
   institutions, and from flat top-50-by-citations to top-cited-*per-field*,
   so a regional/non-R1 school shows up instead of only the already-famous.
   Real Carnegie Classification data is now attached and surfaced as a search
   filter and badge. What's *not* finished: publication/topic enrichment is
   still working through the much larger professor set (a background daily
   pipeline, not a one-time job), so recency filtering stays opt-in until
   that coverage catches up — see Phase 3 below.
5. **Labs don't scale.** Still 45 rows from two hand-pasted directory pages —
   untouched since the original pilot. This is Phase 4, now deliberately
   *after* Phase 6: more content doesn't help until the app is somewhere
   other people can reach it.
6. **No opportunity signal.** Nothing records whether a PI or program actually
   takes students, which is the fact a student most needs. (Phase 5B.)
7. **Nobody outside this machine can use it.** The app only runs on
   `localhost` — this is what Phase 6 closes, and per the user's direction on
   2026-08-08, it now comes before Phase 4/5B/5C: get the existing product in
   front of real students before adding more data or polish.

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

## Phase 3 — Coverage that matches the users (mostly done)

The current slice is the opposite of what an unknown student needs. A high
schooler in Nebraska is not getting a lab spot from a top-50-cited Stanford
PI; they are getting one from a regional state school twenty minutes away.

- ✅ **Widened ingestion beyond the top 100.** `get_us_institutions()` pulls
  every US `type=education` institution above a works-count floor (~1,764
  institutions, vs. the original fixed 100) — masters- and bachelors-granting
  schools included, not just R1s.
- ✅ **Per-institution professor selection is now per-field, not a flat cap.**
  `get_professors_at_institution_by_field()` pulls top-cited-*per-field*
  professors (20 for the largest ~100 institutions, 5 below that — smaller
  schools often don't have 20 genuine matches in a given field), so coverage
  isn't dominated by whichever field happens to be most-cited overall. This
  took `Professor` from ~4,431 to ~196,000 rows.
- ✅ **Institution classification, from real data, not a heuristic.**
  `Institution.carnegie_classification` is backfilled from ACE/Indiana
  University's actual Carnegie Classification dataset (matched by name+city,
  not our own `works_count`), surfaced as both a search filter and a badge on
  result cards/detail pages. This is the "schools near me" signal the
  original bullet asked for.
- ⚠️ **Recency filtering is opt-in, not default, and that's deliberate.**
  `recent_only` (3-year cutoff) shipped, but making it default-on right now
  would hide the large majority of the ~196k professors: publication/topic
  enrichment is a background daily pipeline still working through the much
  larger set (only ~11% had a `Publication` row as of this filter shipping),
  so "no recent publication on file" mostly means "not enriched yet," not
  "inactive." Revisit defaulting it on once that coverage is substantially
  more complete — worth checking again once Phase 6 is done and the
  pipeline's had more uninterrupted time to run.
- **Not done, and not currently planned:** non-US expansion. The API already
  accepts a `country` filter, so this is a config change whenever it becomes
  a priority — no code blocks it.

---

## Phase 4 — Labs, automated (not started; now scheduled after Phase 6)

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

## Phase 5A — Profiles, AI summaries, and cold emails ✅ **done (2026-08-07/08)**

Everything above builds a good directory. This is what makes it a *tool*, and
it's the shortest remaining path to the goal stated at the top: *I have sent a
credible email to a specific person who might say yes.* Phases 3 and 4 make
the directory bigger; this one makes it act.

**Shipped, including some things beyond the original plan below:** professor
detail pages, cached AI summaries (on `gpt-5.4-nano`, swapped from Claude Opus
5 after the feature was built — see `CLAUDE.md`), multi-provider accounts
(Google + email/password) with the verified-email linking rule, student
profiles, cold-email drafting grounded in both sides, and the full frontend
groundwork (DOM helper, style primitives, ES module split). Two things were
added that weren't in the original plan and are worth calling out:
**professor bookmarking** (`Bookmark` table, saved per-student, each joined
to its latest draft) with its own `#/bookmarks` page, and **resume PDF
import** (`POST /api/me/resume`) that extracts profile fields via a
structured-output LLM call and hands them to the frontend to review and save
— never written to `StudentProfile` directly, same "app drafts, student
decides" shape as the cold-email feature itself.

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
names a real paper and a real reason they're a fit. ✅ **This works
end-to-end now** — the remaining gap to the top-of-file goal isn't the
product, it's that only people with `localhost` access can try it, which is
what Phase 6 closes.

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

## Phase 6 — Ship it ← **next up**

Everything above assumes `localhost`. This phase is what stands between that
and a URL a student can open. The architecture is already close — one process
serving API and UI on one origin — so most of the work is configuration,
guardrails, and a handful of specific code changes that only matter once the
database is somewhere else.

**Promoted ahead of Phase 4 (and 5B/5C) on 2026-08-08, at the user's
direction:** get the product that already works end-to-end in front of real
users before adding more content (labs) or polish (redesign). Everything
below this heading — 6.2 through 6.7 — is what's actually left; 6.1 already
shipped.

### 6.1 — Code changes that block deployment ✅ **done (2026-08-07, `2c28df8`)**

These were prerequisites, not polish, and they're done: `get_connection()`
now draws from a `psycopg_pool.ConnectionPool` keyed off `DATABASE_URL`
(falling back to today's local values in dev), released via a
`@db.with_connection` decorator on every DB-touching route — verified this
was necessary rather than request-scoped middleware, since FastAPI runs sync
dependencies and the sync endpoint body as separate threadpool calls with
independently-copied context, so middleware couldn't see what either one
checked out. Stress-tested at 40 concurrent requests / 80 checkouts against a
pool of 10. `GET /healthz` (200 only on a real query) is live, and the
migration path has been verified against a genuinely empty database for the
first time. Session cookie flags (`Secure`, gated on `ENV=production`) landed
alongside the accounts work in Phase 5A rather than here, since that's where
the session gets created — see `backend/sessions.py`.

One remaining open item from the original 6.1 list: **secrets still need to
come from a real platform secret store in production** (`OPENAI_API_KEY`,
`SESSION_SECRET`, `GOOGLE_CLIENT_ID`, the email-provider key), failing loudly
at startup if any are missing — `.env` stays for local dev only. This is
config for whichever host gets picked in 6.2, not a code change.

### 6.2 — Hosting shape

**Decided 2026-08-08: Render (web service) + Neon (Postgres).** Not Render's
own free Postgres — it expires 30 days after creation and gets deleted after
a 14-day grace period if not upgraded, which is not acceptable for data that
cost real OpenAlex/ORCID API time to collect and, per the note below, isn't
quickly reproducible. Neon's free tier persists indefinitely (idles on
inactivity, doesn't delete data). Render's free web service is fine to start
on — 750 free instance-hours/month, sleeps after 15 minutes idle with up to
a ~1-minute cold start on the next request, which is a fine trade for an
early launch with low traffic.

✅ **Docker image and Blueprint written** (`Dockerfile`, `.dockerignore`,
`requirements.txt`, `render.yaml`). `requirements.txt` mirrors
`environment.yml`'s pip section by hand (conda itself isn't needed in the
image — every pip dependency ships a prebuilt wheel, verified by dry-run
installing all of them fresh); `psycopg[binary]` replaces conda's
`psycopg`/`psycopg-c` pair for the same reason. Migrations run at container
start (`python -m database.migrate && uvicorn ...`, baked into the
Dockerfile's `CMD`) rather than as a Render `preDeployCommand` release
step — that field is paid-plan-only, and this service deploys on the free
plan; `database/migrate.py` is idempotent, so re-running it on every boot
(including free-tier cold starts after the instance sleeps) is safe and
cheap. `healthCheckPath: /healthz` wires up the endpoint Phase 6.1 added.
`Makefile` gained `docker-build`/`docker-run` (local sanity check) and
`restore-to-neon` (one-time `pg_dump | psql` move of the local database into
Neon). `.env.example` documents every env var the app reads
and which ones are still required in production.

**Still open, and each needs a real decision/account, not just code:**

- **Create the actual Render and Neon accounts/projects and get a domain
  pointed at Render.** Nothing above deploys itself — `render.yaml` is a
  Blueprint Render reads once you connect the repo. A real domain with TLS
  is not optional: Google OAuth requires registered authorized origins and
  redirect URIs, and `Secure` cookies require HTTPS.
- **Pick a transactional email provider.** `EMAIL_BACKEND` only has a
  `"console"` implementation right now (`backend/email.py`) — anything else
  raises `NotImplementedError`. Fine for smoke-testing the deploy; signup/
  verification/reset emails silently go nowhere a real user can see until
  this is picked and implemented.
- **Move the data.** `make restore-to-neon NEON_URL=...` once the Neon
  project exists. Run `make backup` first regardless.
- **Automated backups going forward**, either Neon's point-in-time recovery
  (check what the free tier actually includes) or a scheduled `pg_dump`.

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
user or one script can spend real money on your API key. This now includes
resume-PDF import (`POST /api/me/resume`), not just summaries and cold
emails — it wasn't in the original plan below but calls the model on every
upload, uncached, same as email drafting.

- **Per-user daily cap on cold-email generation and resume import**, enforced
  server-side. Summaries are naturally bounded because they cache after
  first view; email drafting and resume import are not.
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
4. ~~**Phase 5A**~~ — done (2026-08-07/08). Profiles, AI summaries, accounts,
   cold-email drafting, bookmarking, and resume import all shipped and work
   end to end.
5. ~~**Phase 3 (coverage widening + Carnegie classification)**~~ — done
   alongside 5A. ~1,764 institutions, ~196k professors, per-field sampling,
   real Carnegie data. Recency filtering stays opt-in until publication
   enrichment catches up to the larger set (background daily pipeline,
   ongoing — no action needed, just time).
6. ~~**Phase 6.1**~~ — done (2026-08-07). Pooled connections, `DATABASE_URL`,
   `/healthz`, empty-DB migration check.
7. **Phase 6 (6.2–6.7) — next up, at the user's explicit request.** The
   product works end to end on `localhost`; the only thing separating that
   from "other people can use it" is hosting, secrets, guardrails, and the
   trust/legal basics in 6.5. This is now prioritized **ahead of Phase 4**:
   the goal is to get the app in front of other users before adding more
   content. Suggested internal order: 6.2 (hosting shape) and the remaining
   6.1 secrets item first, since nothing else in Phase 6 works without a
   deployed target → 6.4 (guardrails) before opening it up publicly, since
   the LLM endpoints are live and unmetered right now → 6.5 (trust/legal)
   before real users, not after → 6.3 and 6.6 can trail slightly since
   they're operational rather than blocking.
8. **Phase 4 (labs, automated)** — after Phase 6. More content doesn't help
   until the app is somewhere other people can reach it; this was the
   original point of promoting Phase 6.
9. **Phase 5B** — after Phase 4 (or interleaved, if the high-school /
   structured-program audience turns out to matter more than lab coverage
   once there's real usage to look at).
10. **Phase 5C** — whenever. Not on the critical path, blocks nothing, but
    should keep following 5A/6 rather than precede them.

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
