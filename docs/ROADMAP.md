# Research Finder — Roadmap

**Last updated:** 2026-09-01

> **Phase 6 is fully done — the app is live and the core loop works
> end-to-end for a stranger.** `https://research-finder.com` (Render + Neon),
> Google + password auth, Resend email, every LLM endpoint capped/rate-
> limited, privacy/terms/provenance pages and a contact path, Sentry error
> reporting verified live, and CI running the suite (2,218 tests) on every
> push. The uptime check against `/healthz` stays deferred until there's
> real traffic to protect.
>
> **Phase 6.8 (first-run usability) is done as of 2026-09-01:** verified
> Resend sending domain, landing-page example searches, the merged
> field/topic "Research area" box, zero-results guidance + a
> publication-recency line on every card, the lab-vs-professor copy, and a
> `#/guide` onboarding page (header link + shown once to a new account).
>
> **Next up, in order:**
>
> 1. **Phase 6.9 — Close the enrichment gap.** Publication/topic coverage is
>    still catching up to the ~196k-professor set on a daily pipeline that
>    only runs when one Mac is on. This gates search ranking quality, AI
>    summaries, matching (Phase 7), and defaulting recency filtering on.
> 2. **Phase 7 — Professor–student matching.** From a student's saved
>    profile + location + interests, an LLM proposes a ranked shortlist of
>    aligned professors with a grounded reason for each — so a signed-in
>    student never starts from a blank form.
> 3. **Phase 4 — Labs, automated.** Still 45 hand-pasted rows.
> 4. **Phase 5B — Opportunities** (REU / structured programs), then
>    **Phase 5C — visual redesign**.
>
> Phase numbers are deliberately *not* renumbered: several code comments
> (`src/ingestion/openalex.py`, migration headers) already cite phase
> numbers, and silently shifting them would make those comments point at the
> wrong thing. New work gets the next free number (6.8, 6.9, 7) rather than
> reordering.

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

Because publication/topic enrichment is still catching up to the widened professor set, some things that depend on it (recency filtering, full-text search hit rate for newly-added institutions) are currently opt-in or partial rather than complete — see Phase 3 below, and Phase 6.9 for the plan to close it.

> **Row counts above are as measured 2026-08-08.** The enrichment pipeline
> has run daily since, so `Publication`/`ProfessorTopic` coverage is higher
> now than the "~11%" figure — but it has not been re-measured against
> production, and it only advances on days the pipeline's Mac is on.
> Re-measuring is the first task of Phase 6.9.

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
7. ~~**Nobody outside this machine can use it.**~~ **Fixed in Phase 6.1–6.6**
   (2026-08-08/10). Live at `https://research-finder.com` on Render + Neon,
   with working Google/password sign-in, real email delivery, every LLM
   endpoint guarded against runaway cost/abuse, a privacy policy/terms/data-
   provenance page, a working contact path, verified Sentry error
   reporting, and CI running the test suite on every push. The one
   deliberately-deferred piece (an uptime check) is a "come back once
   there are real users" item, not a blocker — see the top of this file.
8. **The student who arrives doesn't know how to use it.** The loop works,
   but the entry point is a bare form with fields ("field" vs "topic") a
   16-year-old can't tell apart, no examples, no guidance on what a
   realistic ask looks like, and no signal that a profile with no recent
   publications is stale rather than just un-enriched. And verification
   email still sends from Resend's shared domain, so a real signup can land
   in spam. This is Phase 6.8.
9. **A signed-in student still starts cold.** Even with a saved profile, the
   app makes them translate their own interests into search filters. It
   already has interests, level, and location on file — it should be able
   to propose people. This is Phase 7.

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
  location radius. **The professor half of this ships earlier as Phase 7**
  (LLM retrieve-then-rerank over `StudentProfile`); its candidate list is
  built as a typed union so adding `Opportunity` rows here is a data
  change, not a rewrite of the ranking step.

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

## Phase 6 — Ship it ✅ **done (2026-08-07 → 2026-08-10)**

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

✅ The remaining open item from the original 6.1 list — **secrets coming
from a real platform secret store in production** — is also done as of the
6.2 deploy: `DATABASE_URL`, `SESSION_SECRET`, `OPENAI_API_KEY`,
`GOOGLE_CLIENT_ID`/`SECRET`, `RESEND_API_KEY`, and `APP_BASE_URL` all live
in Render's Environment tab, not in a committed file. `.env` stays for
local dev only.

### 6.2 — Hosting shape ✅ **live (2026-08-08)**

The app is deployed and reachable at `https://research-lab-finder.onrender.com`
— `/healthz` returns `{"status": "ok"}`, confirming it's actually querying
Neon, not just that the container booted.

**Two real problems hit and fixed on the way here**, worth remembering for
next time this pattern comes up:

- **Neon's free tier hard-caps a project at 512 MB.** The local database was
  554 MB (`publication` alone is 463 MB), so the first restore attempt
  failed partway through with `project size limit exceeded`, silently
  leaving some tables incomplete. Fixed by upgrading to Neon's usage-based
  Launch plan before restoring — ~$0.19/month in storage at this size, no
  fixed cap. Anyone repeating this migration should check `SELECT
  pg_size_pretty(pg_database_size(...))` against the target tier's limit
  *before* restoring, not after hitting the error mid-load.
- **`requirements.txt`, hand-ported from `environment.yml`'s pip section,
  missed `requests`.** It's a conda-level dependency there (not under
  `pip:`), but `backend/google_auth.py` imports
  `google.auth.transport.requests`, which needs it directly — conda always
  had it installed locally, masking the gap until Render's container
  crashed at import time. Caught for good by installing `requirements.txt`
  into a clean virtualenv (not the conda env) and importing `backend.main`
  directly — the same check should be re-run if `requirements.txt` drifts
  from `environment.yml` again.

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

✅ Render/Neon accounts created, data restored (all ~196k professors, all
1,768 institutions confirmed present after the size-limit fix above), and
the Blueprint is deployed and live.

**Still open, and each needs a real decision/account, not just code:**

✅ **Domain live (2026-08-08).** `research-finder.com` (bought via Namecheap,
renamed from the original "Research Lab Finder" branding the same day — see
below) and `www.research-finder.com` both point at Render with verified TLS.
Google OAuth's Authorized JavaScript origins updated to include both, fixing
Google Sign-In in production.

✅ **Email provider picked and wired up (2026-08-08): Resend.** Chosen over
Postmark (100 emails/month free tier, too tight even at low signup volume)
and SendGrid (dropped its permanent free tier in 2025 — trial only now) for
Resend's 3,000-emails/month free tier, which is permanent rather than
time-limited. `backend/email.py` gained an `EMAIL_BACKEND=resend` branch —
`build_resend_payload()` is a pure function (tested in `tests/test_email.py`
without a network call, same pattern as `build_search_query()`), the actual
`requests.post()` to Resend's API is the thin impure wrapper around it.
`render.yaml` sets `EMAIL_BACKEND=resend` with `RESEND_API_KEY` prompted as
a secret. ✅ **Resolved (2026-09-01):** `research-finder.com` is a verified
Resend sending domain (SPF/DKIM published), `EMAIL_FROM` is set to
`Research Finder <noreply@research-finder.com>` in Render, and
`backend/email.py` now defaults to that same address so a missing env var
degrades safely rather than to the shared `onboarding@resend.dev` testing
domain. Signup → verification email → confirmed account was tested
end-to-end against production and the email lands in the inbox.

- **Automated backups going forward**, either Neon's point-in-time recovery
  (check what the Launch plan actually includes) or a scheduled `pg_dump`.

### 6.3 — Where the ingestion pipeline runs ✅ **decided and wired up (2026-08-08)**

**Keep it local, pointed at the production database** — the enrichment
pipeline still runs as three launchd agents on a personal Mac
(`launchd/*.plist`), but as of the Render/Neon deploy, all three wrapper
scripts (`scripts/run_enrich_names.sh`, `run_publications_daily.sh`,
`run_topics.sh`) source a gitignored `.env.production` file (if present)
before running, which sets `DATABASE_URL` to the Neon connection string.
Enrichment now writes straight to production, so there's no separate local
copy of `Institution`/`Professor`/`Publication`/`ResearchTopic` data that
needs a manual `pg_dump`/restore to sync — that was the actual motivating
problem (Neon's snapshot going stale the moment daily enrichment keeps
running locally). Deliberately **not** the shared root `.env` — that one
still controls local dev/`uvicorn`/tests, which should keep defaulting to
local Postgres unless someone opts in explicitly. Zero new infrastructure,
preserves the rate-limit circuit breakers and daily-resume scheduling
already tuned in those plists; the known downside is unchanged — it only
runs when that Mac is on. **To set up:** create `.env.production` at the
repo root containing one line, `DATABASE_URL=<Neon connection string>`.

**Still available if the "only runs when the Mac is on" downside becomes a
real problem:** move to platform cron (Render cron jobs, Fly scheduled
machines, or GitHub Actions on a schedule) — the scripts are already
independent module entry points, so this would be a scheduling change, not
a rewrite.

### 6.4 — Guardrails before real users ✅ **done (2026-08-09)**

The LLM endpoints from Phase 5A change the risk profile. Without limits, one
user or one script can spend real money on your API key. This now includes
resume-PDF import (`POST /api/me/resume`), not just summaries and cold
emails — it wasn't in the original plan below but calls the model on every
upload, uncached, same as email drafting.

- ✅ **Per-user daily cap on cold-email generation and resume import
  (2026-08-08).** Summaries are naturally bounded because they cache after
  first view; these two are not, so nothing else was stopping one user or
  script from generating in a loop. Backed by a new `LlmUsage` table
  (migration `007_llm_usage.sql`: `user_id`, `kind`, `created_at`) rather
  than an in-process counter like `backend/rate_limit.py`'s auth limiting —
  this is a real spend guard, not just an abuse nuisance guard, so it needs
  to survive a Render free-tier cold start mid-day rather than silently
  resetting. Cold email: 20/day (`COLD_EMAIL_DAILY_LIMIT` in
  `backend/main.py`). Resume import: 5/day (`RESUME_IMPORT_DAILY_LIMIT` in
  `backend/auth.py`) — tighter, since a legitimate student realistically
  imports their resume once, maybe retries a couple of times, not
  routinely. A usage row is recorded on a real (billed) API call whether it
  succeeds or the model refuses — only the "not configured" case (caught
  before any API call) doesn't count.
- ✅ **Monthly spend alert set (2026-08-09): $20/month** on the OpenAI
  account (Settings → Billing → Limits). Worth noting since it changes what
  this guardrail actually does: as of early 2026, OpenAI's monthly budget
  threshold no longer hard-stops API access when hit — it sends an email
  and a dashboard banner while requests keep going through and billing
  continues. So this is an early-warning tripwire, not a hard cap; it's the
  per-user daily caps above (Phase 6.4) and rate limiting that actually
  bound worst-case cost, this just makes sure a runaway loop gets noticed
  quickly rather than showing up as a surprise invoice.
- ✅ **Rate limits on auth endpoints (2026-08-08).** `login`, `signup`, and
  `forgot` are all limited by both email and IP, via a small in-process
  fixed-window counter (`backend/rate_limit.py`) rather than slowapi/limits
  (those key off the raw Starlette `Request`, which makes limiting by a POST
  body field like email awkward) or Redis (this app runs a single Render
  instance with no horizontal scaling, so there's no state to share across
  processes — a counter reset on a cold start is a non-issue for an abuse
  guard). Login uses a tighter, shorter window (8/15min per email, 30/15min
  per IP) since brute-forcing a password is rapid-fire; signup/forgot use a
  longer one (3/hour per email, 10/hour per IP) since their abuse shape is
  spamming a real inbox with unwanted email, not guessing a secret — the
  exact nuisance found and confirmed live before this was built (see
  Phase 5A's account-linking notes above). A 429 is returned generically,
  same anti-enumeration principle as the rest of this file.
- ✅ **Treat email drafting as a spam vector — satisfied.** It generates
  persuasive messages addressed to real named academics. The mitigation
  (account required, a daily cap, and the send action staying manual — the
  app drafts, the student sends) is now fully in place: accounts were
  already required from Phase 5A, the daily cap landed above, and there has
  never been a "send for me" button. Keep it that way — don't add one.

### 6.5 — Trust, and the fact that this app is about real people ✅ **done (2026-08-10)**

Every row is a real named academic who did not sign up for this. The data is
public and properly attributed, but shipping to strangers raises obligations
that a localhost prototype doesn't have.

- ✅ **Privacy policy and terms** (`#/privacy`, `#/terms`, `frontend/views/
  legal.js`), covering what's stored for accounts, and — the part that
  actually needed writing carefully — what the AI features (summaries,
  cold-email drafts, resume import) send to the outside model provider,
  including that a student's profile text and resume are part of that
  payload.
- ✅ **Data provenance stated on-site** (`#/about`, same file): OpenAlex and
  ORCID as sources (both public), the attribution method that avoids the
  original misattribution bug, and that AI-generated text is always labeled
  as such — per the principle below.
- ✅ **A working contact path for correction or removal requests.** Two
  paths now exist side by side: the existing per-professor "Flag an issue"
  button (`backend/flags.py`, already live from earlier work) for anything
  tied to one Professor row, and a new general contact form (`#/contact`,
  `POST /api/contact`, `backend/contact.py`) for anything else — a
  professor asking to be removed entirely, or a privacy question. Both
  email `ADMIN_EMAIL` through the existing `send_email()` seam
  (`backend/email.py`); the contact form is IP-rate-limited (5/hour, same
  `backend/rate_limit.py` used by auth) since, unlike a flag, it has no
  account and no per-email limit worth enforcing. All four pages are linked
  from a new site footer (`frontend/index.html`).

### 6.6 — Knowing when it breaks ✅ **done (2026-08-10; uptime check deferred)**

- ✅ **Error reporting -- done and verified live (2026-08-10).** `backend/
  error_reporting.py`'s `init_sentry()` wires up Sentry's Python SDK, called
  once before the `FastAPI()` app object is constructed so its Starlette/
  FastAPI auto-instrumentation (enabled automatically once `sentry-sdk`
  detects those packages -- no explicit `integrations=[...]` needed) can
  patch what it needs to. No-ops when `SENTRY_DSN` is unset, same
  "optional feature degrades gracefully" pattern as `OPENAI_API_KEY`/
  `RESEND_API_KEY` -- dev and tests never talk to Sentry. `send_default_pii`
  stays at the SDK's own `False` default (this app handles real personal
  data -- student profile text, resumes, session cookies -- and an error
  report is the last place that should end up), and `scrub_event()` is a
  second, tested layer on top of that: it strips any `Authorization`/
  `Cookie` header from an event's request context regardless, so the
  guarantee doesn't depend on `send_default_pii` never getting flipped on
  later. `traces_sample_rate=0` -- error capture only, no performance
  tracing, comfortably inside the free tier regardless of traffic. Sentry
  project created, `SENTRY_DSN` set in Render, and verified two ways: a
  standalone script capture (confirms the DSN/network path) and a real
  request against a deliberately-raising route hit live in production
  (confirms the FastAPI auto-instrumentation path too) -- both showed up in
  the Sentry dashboard. The route was temporary and has been removed.
- An uptime check against `/healthz`. **Deliberately skipped for now** --
  not enough real users yet for "the site went down" to need an automated
  page; revisit once there's real traffic to protect.
- ✅ **CI running `python -m pytest` on push (2026-08-10).**
  `.github/workflows/ci.yml` runs the full suite on every push/PR against
  `main`. `render.yaml` has `autoDeploy: true`, so a merge to `main`
  deploys straight to production with nothing else forcing the suite to
  run first -- this is what actually closes that gap, rather than relying
  on remembering to run `pytest` locally before merging. Plain pip, not
  conda: a conda solve is unnecessary weight for CI (same reasoning as
  `requirements.txt` for the Docker image), and `environment.yml`'s
  conda-level pins include at least one macOS-only package (`libcxx`)
  that wouldn't resolve on the Linux runner anyway. New
  `requirements-dev.txt` layers `pytest`/`pyalex`/`openpyxl` on top of
  `requirements.txt` -- the first is dev/CI-only by design (see
  `requirements.txt`'s own comment), the latter two are conda-env pip
  dependencies for the local ingestion pipeline that several *tests*
  still import (`tests/test_openalex.py`, `tests/test_carnegie.py`) even
  though production code never touches them. Verified by running the
  suite in a throwaway plain-`venv` (not conda) locally first, to catch
  exactly this kind of missing-dependency gap before trusting the actual
  CI run.

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
user telling you. ✅ **This is true now.** Phases 6.8–6.9 below are about the
students who arrive after that being able to *succeed*, not just complete
the mechanical steps.

### 6.8 — First-run usability ✅ **done (2026-09-01)**

The loop works for someone who already knows what the app is and how to use
it — i.e. the person who built it. A first-time high schooler lands on a
bare form with jargon fields and no idea what a good search or a realistic
ask looks like. Each item below is small; together they're the difference
between "technically usable" and "a stranger gets a result."

- ✅ **Verified sending domain (2026-09-01).** `research-finder.com` is
  verified in Resend with SPF/DKIM published, `EMAIL_FROM` is set to
  `Research Finder <noreply@research-finder.com>` in Render (and is now the
  `backend/email.py` fallback too), and signup → verification → confirmed
  account was tested end-to-end against production with the email landing in
  the inbox. This was the "live bug" carried over from Phase 6.2.
- ✅ **Onboarding guidance (2026-09-01).** `#/guide` (`frontend/views/
  guide.js`) — a short static page covering what a search returns
  (individual PIs, not a curated lab list), that most professors have no
  public email so the contact panel's Scholar/site-search links are the
  path, what a credible first email looks like, and what an account adds.
  Linked from the header ("How it works", new `.site-nav`). Shown once to a
  new account: the email-verification view routes fresh password signups to
  `#/guide?welcome=1`, and `app.js` redirects any signed-in user who lands
  on root without the `rf_seen_guide` localStorage flag (covers Google's
  first sign-in, which has no post-signup step to hook). Only fires on a
  root landing, so it never hijacks a deep or verification link.
- ✅ **Example searches on the landing page (2026-09-01).** Six clickable
  chips under the hero (`machine learning · Boston`, `neuroscience ·
  California`, `materials science · Texas`, `robotics · Michigan`, `marine
  biology · Florida`, `climate science · Washington`) that fill the form and
  run a real search (`EXAMPLE_SEARCHES` / `applyExample` in
  `frontend/views/search.js`, reusing the existing `.chip-button` style).
  Each maps only to filters search actually supports — a topic plus one
  location dimension — and opens the advanced section when it fills
  city/state so the applied filter is visible.
- ✅ **Made the field/topic distinction legible (2026-09-01).** Collapsed
  the "Field" `<select>` and "Research topic" input into one "Research area"
  text box (name still `topic`, so `build_search_query()`'s existing
  ILIKE-match against ResearchTopic name/field/subfield covers both levels)
  with helper text spelling out that a broad field or a specific topic both
  work. The field-scoped topic autocomplete went away with the `<select>`;
  autocomplete is now unscoped. `/api/fields` and `listTopics`' `field`
  param are left in place for a possible future facet but are no longer
  called from the search form. Frontend-only change — `search.js`.
- ✅ **Better empty and stale states (2026-09-01).** Zero results now
  render a dashed guidance card (`emptyStateCard()` in `search.js`) that
  lists concrete filters to relax, chosen from whichever are actually set
  (institution, location, institution type, publication-text, recent-only)
  plus a "try a broader research area" fallback; paging past the last page
  shows "You've reached the end" instead. And every result card and the
  detail hero carry a `recencyLine()` (`professor.js`): "Last published
  20XX" from `/api/search`'s `last_publication_date` (already returned per
  row) / the max date of the detail page's loaded publications, or "No
  publications on file yet — this profile may not be fully enriched" when
  there's no date — deliberately not "inactive", since null means
  un-enriched here. Frontend-only.
- ✅ **Reconciled the "lab" vs "professor" framing (2026-09-01).** The hero
  now reads "Find a research professor" / "Search individual professors by
  research field, topic, institution, or location", and the privacy page's
  one-line description was updated to match. Revisit once Phase 4 gives
  `Lab` real coverage.

**Done when** a student who has never seen the app can land on it, understand
what it does, run a sensible search from an example, and read a result
without needing anything explained.

### 6.9 — Close the enrichment gap

Publication/topic enrichment has been a background daily pipeline since
Phase 3 widened `Professor` to ~196k. It gates real things: search ranking
quality (topic/text rank need the data), AI summaries (`insufficient_data`
when a professor has neither), Phase 7 matching (same), and whether
`recent_only` can default on. It also only advances on days the pipeline's
Mac is powered on.

- **Re-measure coverage against production.** `Publication` /
  `ProfessorTopic` / `ResearchTopic` row counts and the share of
  professors with ≥1 of each, versus the "~11%" last measured 2026-08-08.
  This number decides how much of the rest of this phase is urgent.
- **Move the pipeline off the personal Mac.** The three wrapper scripts
  are already standalone module entry points sourcing `.env.production`;
  this is a scheduling change, not a rewrite — GitHub Actions on a cron,
  or Render/Fly scheduled jobs. Removes the "only runs when the Mac is on"
  ceiling that Phase 6.3 explicitly left open.
- **Prioritise enrichment by demand, not uniformly.** Enrich professors in
  the most-searched fields/institutions first (needs the search-term
  logging from 6.8's analytics, or a simple ordering by institution
  works_count as a proxy) so the slices students actually hit fill in
  before the long tail.
- **Then default `recent_only` on**, with a result count and an easy
  toggle off — the Phase 3 note said to revisit this "once the pipeline's
  had more uninterrupted time to run," and that's this.

**Done when** a typical search returns mostly enriched, ranked results, an
AI summary is available for most professors a student would actually open,
and the pipeline keeps running whether or not a specific laptop is awake.

### Later, once people actually return

- Saved searches and "email me new matches in my field near me" — the
  feature that turns a one-time visit into a returning user. Worth building
  after there's evidence people come back at all.

---

## Phase 7 — Professor–student matching

Search makes a student translate what they want into filters. By the time
they've signed in and filled a `StudentProfile`, the app already knows their
interests, level, location, techniques, and what they're looking for — it
should be able to hand them a ranked shortlist of specific professors with a
plain-language reason for each, so the starting point is *"here are ten
people, here's why"* rather than an empty form.

This is the professor half of what Phase 5B's "ranked matches across
professors and opportunities" describes; building it now (professors only)
means the retrieve-then-rank machinery already exists when Opportunities
land, and it's the single biggest lever on the top-of-file goal for a
signed-in student.

### Shape

**Two stages — retrieval, then rerank. Never send 196k professors to a
model.**

1. **Candidate retrieval (SQL, no LLM).** Derive structured filters from the
   profile — topic/field from stated interests, city/state or a metro
   radius from location, optionally institution type — and reuse the
   existing `build_search_query()` path to pull the top ~30–50 candidates by
   today's relevance ranking (topic `works_count`, then text rank, then
   recency). A new pure `build_candidate_filters(profile)` in
   `backend/matching.py` does the profile → params mapping.
2. **LLM rerank + rationale.** Pass the profile plus those ~30 candidates
   (name, institution, location, topics, a few recent publication
   titles/abstracts) to the model via structured output; it returns an
   ordered subset (say the top 10) each with a 1–2 sentence reason grounded
   **only** in the supplied topics/publications — *"works on protein-design
   methods, which matches your stated interest in computational biology;
   2025 paper on X"* — not invented biography. `build_match_prompt(profile,
   candidates)` is the pure prompt assembler.

### Rules it inherits from the rest of the project

- **Absent beats wrong.** A candidate with no enriched topics/publications
  can still rank on filters but gets no fabricated rationale. The model may
  return fewer than N. If retrieval finds nothing (niche interest + small
  metro), return an empty list with a `reason`, not a padded one — same as
  the summary endpoint's `insufficient_data`.
- **Profile text is untrusted input** (the Phase 5A prompt-injection rule).
  The rerank endpoint only ranks and explains; it never acts on its own
  output.
- **Cache it.** New `StudentProfile.matches_json` + `matches_generated_at`
  (migration `012_*.sql`), keyed to a hash of the profile inputs.
  Regenerate when the profile changes, on an explicit "refresh", or past an
  age cutoff — same lazy, no-batch-job pattern as AI summaries.
- **Cap it.** It's an uncached LLM call over a biggish prompt, so give it a
  per-user daily cap via the existing `LlmUsage` table (`kind='match'`),
  same as cold-email and resume import. Only billed calls count.
- **Split for testability.** `build_candidate_filters()` and
  `build_match_prompt()` are pure and covered in `tests/test_matching.py`
  (no DB, no network); `generate_matches()` — the API call — isn't
  unit-tested, mirroring `generate_summary()` and the OpenAlex fetchers.
- **New `/api/*` endpoint, opt-in from the frontend.** `GET /api/me/matches`
  behind `current_user`, requires a saved profile. The search path keeps
  zero external dependencies and no added latency for signed-out users.

### Frontend

A `#/matches` view (and a section on the signed-in home view for a student
who has a profile): ranked cards reusing the existing result-card component
plus the rationale line, each linking to the professor detail page. A
student with no profile yet sees a prompt linking to the profile form. The
rationale is labelled AI-generated, like every other model output on the
site.

### Relation to Phase 5B

Build the candidate list as a typed list of items, not a professors-only
array, so that when `Opportunity` rows exist the same rerank step ranks
opportunities alongside professors with no change to the prompt shape.

**Done when** a signed-in student with a filled profile lands on the app and
sees ~10 specific, plausibly-matched professors — each with a real,
grounded reason — without touching the search form.

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
7. ~~**Phase 6.1, 6.2, 6.3, 6.4**~~ — all done as of 2026-08-09. Deployed
   live at `https://research-finder.com` (Render + Neon), Google OAuth
   fixed for the real domain, Resend wired up for real email delivery,
   local ingestion pointed at production, and every LLM endpoint is now
   capped/rate-limited (auth endpoints by IP+email, cold-email/resume
   import by a daily per-user cap, plus a $20/month OpenAI spend alert as
   an early-warning tripwire on top of those).
8. ~~**Phase 6.5**~~ — done 2026-08-10 (trust/legal): privacy policy, terms,
   an on-site data-provenance page, and a contact path for correction/
   removal requests alongside the existing per-professor flag feature.
9. ~~**Phase 6.6**~~ — done 2026-08-10 (monitoring): Sentry error reporting
   wired up and verified live in production, and CI running the test
   suite on every push. The uptime check is deliberately deferred until
   there's enough real traffic for it to matter; 6.7 is just a cost
   writeup, not an action item.
10. ~~**Phase 6.8 (first-run usability)**~~ — done 2026-09-01. Verified
    sending domain (was a live bug), a `#/guide` onboarding page (header
    link + shown once to new accounts), landing-page example-search chips,
    the merged field/topic "Research area" box, zero-results guidance plus
    a publication-recency line on every result, and the lab-vs-professor
    copy fix.
11. **Phase 6.9 (close the enrichment gap)** ← **next up.** Re-measure production
    coverage, move the pipeline off the personal Mac, prioritise enrichment
    by demand, then default `recent_only` on. Gates ranking quality, AI
    summaries, and Phase 7.
12. **Phase 7 (professor–student matching)** — LLM-ranked shortlist from a
    student's saved profile + location + interests. Needs 6.9's coverage to
    be worth much; do it after. Biggest single lever on the goal for a
    signed-in student.
13. **Phase 4 (labs, automated)** — more content doesn't help until the
    arriving students can already succeed with what's there (6.8–7).
14. **Phase 5B (opportunities)** — after Phase 4, or interleaved / promoted
    ahead of it if real usage shows the high-school / structured-program
    audience matters more than lab coverage. Phase 7's rerank step is built
    to extend to opportunities when they exist.
15. **Phase 5C (visual redesign)** — whenever. Not on the critical path,
    blocks nothing, but should keep following 5A/6 rather than precede them.

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
