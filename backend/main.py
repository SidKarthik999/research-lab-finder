"""FastAPI search backend for Research Lab Finder.

Serves the search API under /api/* and the static frontend (../frontend)
at /. The search path itself (/api/search and friends) is pure SQL
filtering, no LLM involved -- see CLAUDE.md for the data model.

Institution, Professor, Publication, and (as of Phase 1) ResearchTopic
exist. Lab is also live but not yet surfaced here. Accounts (Phase 5A)
are handled by backend/auth.py, mounted below. Professor detail and the
cached AI summary (also Phase 5A) are the one place this file calls an
LLM -- see backend/llm.py.

Run from the repo root: uvicorn backend.main:app --reload
"""

import os
from contextlib import asynccontextmanager
from pathlib import Path

from dotenv import load_dotenv
from fastapi import Depends, FastAPI, HTTPException, Query
from fastapi.staticfiles import StaticFiles
from starlette.middleware.sessions import SessionMiddleware

from backend.auth import router as auth_router
from backend.llm import (
    ColdEmailGenerationNotConfigured,
    ColdEmailGenerationRefused,
    SummaryGenerationNotConfigured,
    SummaryGenerationRefused,
    generate_cold_email,
    generate_summary,
)
from backend.sessions import current_user
from src import database as db
from src.database import get_connection

load_dotenv()


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Opens the DB connection pool once at process startup and closes it at
    # shutdown, rather than each request/thread opening its own connection
    # and holding it forever -- see src/database.py and
    # docs/ROADMAP.md Phase 6.1.
    db.init_pool()
    yield
    db.close_pool()


app = FastAPI(title="Research Lab Finder API", lifespan=lifespan)

# https_only requires ENV=production (and therefore HTTPS) to be set --
# never enforced in local dev, where the app is served over plain HTTP.
# SESSION_SECRET has no default: a missing one fails loudly at startup
# rather than silently signing cookies with a guessable key.
app.add_middleware(
    SessionMiddleware,
    secret_key=os.environ["SESSION_SECRET"],
    same_site="lax",
    https_only=os.environ.get("ENV") == "production",
)
app.include_router(auth_router)


RECENT_YEARS_CUTOFF = 3

def build_search_query(
    name=None,
    text=None,
    institution=None,
    city=None,
    state=None,
    country=None,
    topic=None,
    field=None,
    recent_only=False,
    carnegie_classification=None,
    page=1,
    limit=20,
):
    """Builds the parameterized /api/search SQL and its params, kept apart
    from query execution so the placeholder/param alignment -- easy to get
    subtly wrong when several optional filters each contribute their own
    %s placeholders across multiple SQL fragments -- can be tested without a
    database connection.

    name and text used to be a single combined "keyword" field that silently
    OR'd together professor-name, institution-name, topic, and publication
    full-text matching. Institution and topic/field now have their own
    dedicated filters, so folding those into a "keyword" box was redundant;
    what it uniquely offered -- searching by a professor's own name, and
    free-text search over publication abstracts (finer-grained than the
    curated topic taxonomy) -- are kept as two clearly-scoped filters instead.

    recent_only is opt-in (default False), not a default-on filter, even
    though the roadmap's Phase 3 goal is exactly "don't surface retired/
    inactive PIs". As of the Phase 3 coverage widening (100 -> 1,768
    institutions, ~4.4k -> ~196k professors), publication ingestion is still
    catching up -- only ~11% of professors have any Publication row yet, not
    because the other 89% are inactive, but because the enrichment pipeline
    hasn't reached them. A default-on filter would silently hide the large
    majority of real, active professors behind incomplete data -- the same
    "absent beats wrong" reasoning as everywhere else in this project, just
    applied to a filter rather than a stored fact. Once publication coverage
    is substantially more complete, revisit whether this should flip to
    default-on.
    """
    conditions = []
    params = []

    if name:
        conditions.append("Professor.name ILIKE %s")
        params.append(f"%{name}%")
    if text:
        conditions.append(
            """EXISTS (
                SELECT 1 FROM ProfessorPublication pp
                JOIN Publication pub ON pub.id = pp.publication_id
                WHERE pp.professor_id = Professor.id
                  AND pub.search_vector @@ websearch_to_tsquery('english', %s)
            )"""
        )
        params.append(text)
    if institution:
        conditions.append("Institution.name ILIKE %s")
        params.append(f"%{institution}%")
    if city:
        conditions.append("Institution.city ILIKE %s")
        params.append(f"%{city}%")
    if state:
        conditions.append("Institution.state ILIKE %s")
        params.append(f"%{state}%")
    if country:
        conditions.append("Institution.country_code ILIKE %s")
        params.append(f"%{country}%")
    if topic:
        # OpenAlex's taxonomy is domain > field > subfield > (specific) topic
        # name -- there's rarely a topic literally named "Computer Science" or
        # "Neuroscience", only specific topics under that field/subfield. This
        # filter is meant to be the general-purpose "research area" box, so it
        # matches all three levels rather than just the narrowest one.
        conditions.append(
            """EXISTS (
                SELECT 1 FROM ProfessorTopic pt
                JOIN ResearchTopic rt ON rt.id = pt.topic_id
                WHERE pt.professor_id = Professor.id
                  AND (rt.name ILIKE %s OR rt.field ILIKE %s OR rt.subfield ILIKE %s)
            )"""
        )
        like = f"%{topic}%"
        params.extend([like, like, like])
    if field:
        conditions.append(
            """EXISTS (
                SELECT 1 FROM ProfessorTopic pt
                JOIN ResearchTopic rt ON rt.id = pt.topic_id
                WHERE pt.professor_id = Professor.id AND rt.field ILIKE %s
            )"""
        )
        params.append(f"%{field}%")
    if carnegie_classification:
        # Exact match, not ILIKE -- the values come from the
        # /api/institution-classifications dropdown (see list_institution_classifications
        # below), and several real labels are substrings of each other (e.g.
        # "Doctoral Universities: High Research Activity" is a substring of
        # "...Very High Research Activity"), so a partial match would
        # silently conflate genuinely different tiers.
        conditions.append("Institution.carnegie_classification = %s")
        params.append(carnegie_classification)
    if recent_only:
        # A fixed interval, not a %s placeholder -- RECENT_YEARS_CUTOFF is a
        # server-side constant, never user input, so there's nothing here
        # that needs parameterizing.
        conditions.append(
            f"""EXISTS (
                SELECT 1 FROM ProfessorPublication pp
                JOIN Publication pub ON pub.id = pp.publication_id
                WHERE pp.professor_id = Professor.id
                  AND pub.publication_date >= CURRENT_DATE - INTERVAL '{RECENT_YEARS_CUTOFF} years'
            )"""
        )

    where_clause = f"WHERE {' AND '.join(conditions)}" if conditions else ""
    offset = (page - 1) * limit

    # Ranking signals, one row per professor:
    #  - topic_score: OpenAlex's per-topic works_count for whichever topic
    #    matched (via topic= or field=) -- how central that subject actually
    #    is to this professor's own work.
    #  - text_rank: how well their publications match the free-text search.
    #  - last_publication_date: recency, as the final tie-breaker, so
    #    inactive/retired professors don't rank above active ones.
    rank_conditions = []
    rank_params = []
    if topic:
        rank_conditions.append("(rt.name ILIKE %s OR rt.field ILIKE %s OR rt.subfield ILIKE %s)")
        like = f"%{topic}%"
        rank_params.extend([like, like, like])
    if field:
        rank_conditions.append("rt.field ILIKE %s")
        rank_params.append(f"%{field}%")
    topic_rank_where = f"AND ({' OR '.join(rank_conditions)})" if rank_conditions else "AND FALSE"
    # Used to prioritize matching topics in the "topics" chip list below, so
    # a professor surfaced by a topic/field match shows *that* topic first
    # rather than whatever their single largest topic happens to be.
    topic_match_expr = " OR ".join(rank_conditions) if rank_conditions else "FALSE"

    query = f"""
    SELECT
        Professor.id,
        Professor.name AS professor_name,
        Professor.email,
        Professor.website,
        Professor.orcid,
        Institution.name AS institution_name,
        Institution.website AS institution_website,
        Institution.city,
        Institution.state,
        Institution.country_code,
        Institution.carnegie_classification,
        COALESCE(topic_rank.topic_score, 0) AS topic_score,
        COALESCE(text_rank.rank, 0) AS text_rank,
        recency.last_publication_date,
        COALESCE(top_topics.names, ARRAY[]::text[]) AS topics
    FROM Professor
    LEFT JOIN Institution ON Institution.id = Professor.institution_id
    LEFT JOIN LATERAL (
        SELECT MAX(pt.works_count) AS topic_score
        FROM ProfessorTopic pt
        JOIN ResearchTopic rt ON rt.id = pt.topic_id
        WHERE pt.professor_id = Professor.id
        {topic_rank_where}
    ) topic_rank ON TRUE
    LEFT JOIN LATERAL (
        SELECT MAX(ts_rank(pub.search_vector, websearch_to_tsquery('english', %s))) AS rank
        FROM ProfessorPublication pp
        JOIN Publication pub ON pub.id = pp.publication_id
        WHERE pp.professor_id = Professor.id
          AND pub.search_vector @@ websearch_to_tsquery('english', %s)
    ) text_rank ON TRUE
    LEFT JOIN LATERAL (
        SELECT MAX(pub.publication_date) AS last_publication_date
        FROM ProfessorPublication pp
        JOIN Publication pub ON pub.id = pp.publication_id
        WHERE pp.professor_id = Professor.id
    ) recency ON TRUE
    LEFT JOIN LATERAL (
        SELECT ARRAY_AGG(top3.name ORDER BY top3.match_rank, top3.works_count DESC NULLS LAST) AS names
        FROM (
            SELECT
                rt.name,
                pt.works_count,
                CASE WHEN ({topic_match_expr}) THEN 0 ELSE 1 END AS match_rank
            FROM ProfessorTopic pt
            JOIN ResearchTopic rt ON rt.id = pt.topic_id
            WHERE pt.professor_id = Professor.id
            ORDER BY match_rank, pt.works_count DESC NULLS LAST
            LIMIT 3
        ) top3
    ) top_topics ON TRUE
    {where_clause}
    ORDER BY topic_score DESC, text_rank DESC, recency.last_publication_date DESC NULLS LAST, Professor.name
    LIMIT %s OFFSET %s;
    """

    all_params = [*rank_params, text, text, *rank_params, *params, limit, offset]

    return query, all_params


@app.get("/api/search")
@db.with_connection
def search_professors(
    name: str | None = Query(None, description="Match against the professor's own name"),
    text: str | None = Query(None, description="Free-text search over publication titles and abstracts"),
    institution: str | None = None,
    city: str | None = None,
    state: str | None = None,
    country: str | None = None,
    topic: str | None = Query(None, description="Filter by research topic name"),
    field: str | None = Query(None, description="Filter by research field, e.g. 'Physics and Astronomy'"),
    recent_only: bool = Query(
        False, description="Only professors with a publication in the last few years"
    ),
    carnegie_classification: str | None = Query(
        None, description="Filter by the institution's Carnegie Classification, e.g. 'Doctoral Universities: Very High Research Activity'"
    ),
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
):
    query, all_params = build_search_query(
        name=name,
        text=text,
        institution=institution,
        city=city,
        state=state,
        country=country,
        topic=topic,
        field=field,
        recent_only=recent_only,
        carnegie_classification=carnegie_classification,
        page=page,
        limit=limit,
    )

    connection = get_connection()
    cursor = connection.cursor()
    cursor.execute(query, all_params)
    columns = [desc.name for desc in cursor.description]
    rows = [dict(zip(columns, row)) for row in cursor.fetchall()]
    cursor.close()
    return {"results": rows, "page": page, "limit": limit}


@app.get("/api/fields")
@db.with_connection
def list_fields():
    # Unlike /api/topics (2,400+ distinct topic names -- autocomplete makes
    # sense) or /api/institutions, ResearchTopic.field is OpenAlex's top-level
    # taxonomy: ~26 fixed values. Small and stable enough for a dropdown to
    # just fetch and show all of, no query/limit/pagination needed.
    connection = get_connection()
    cursor = connection.cursor()
    cursor.execute("SELECT DISTINCT field FROM ResearchTopic WHERE field IS NOT NULL ORDER BY field;")
    fields = [row[0] for row in cursor.fetchall()]
    cursor.close()
    return {"fields": fields}


@app.get("/api/institution-classifications")
@db.with_connection
def list_institution_classifications():
    # Same shape as /api/fields: a small, fixed set of values (Carnegie's
    # own Basic Classification taxonomy, ~33 possible labels, a subset of
    # which actually appear in our data) -- a dropdown, not an
    # autocomplete-as-you-type box. Only ~78% of institutions have been
    # matched (see src/ingestion/carnegie.py); this only returns values that
    # actually appear, so the dropdown never offers an option that would
    # return zero results.
    connection = get_connection()
    cursor = connection.cursor()
    cursor.execute(
        "SELECT DISTINCT carnegie_classification FROM Institution "
        "WHERE carnegie_classification IS NOT NULL ORDER BY carnegie_classification;"
    )
    classifications = [row[0] for row in cursor.fetchall()]
    cursor.close()
    return {"classifications": classifications}


@app.get("/api/topics")
@db.with_connection
def list_topics(
    q: str | None = None,
    field: str | None = Query(None, description="Scope suggestions to topics under this field"),
    limit: int = Query(20, ge=1, le=100),
):
    conditions = []
    params = []
    if q:
        conditions.append("name ILIKE %s")
        params.append(f"%{q}%")
    if field:
        conditions.append("field = %s")
        params.append(field)
    where_clause = f"WHERE {' AND '.join(conditions)}" if conditions else ""

    connection = get_connection()
    cursor = connection.cursor()
    cursor.execute(
        f"SELECT DISTINCT name FROM ResearchTopic {where_clause} ORDER BY name LIMIT %s;",
        [*params, limit],
    )
    topics = [row[0] for row in cursor.fetchall()]
    cursor.close()
    return {"topics": topics}


def _fetch_professor_topics(cursor, professor_id, limit=None):
    query = """
        SELECT ResearchTopic.name, ResearchTopic.field, ResearchTopic.subfield, ProfessorTopic.works_count
        FROM ProfessorTopic
        JOIN ResearchTopic ON ResearchTopic.id = ProfessorTopic.topic_id
        WHERE ProfessorTopic.professor_id = %s
        ORDER BY ProfessorTopic.works_count DESC NULLS LAST
    """
    params = [professor_id]
    if limit is not None:
        query += " LIMIT %s"
        params.append(limit)
    cursor.execute(query, params)
    columns = [desc.name for desc in cursor.description]
    return [dict(zip(columns, row)) for row in cursor.fetchall()]


def _fetch_recent_publications_with_abstracts(cursor, professor_id, limit=8):
    # Separate from professor_publications()'s query below because that one
    # returns every publication for the reading-list display (no LIMIT) and
    # this one is capped for the summary/cold-email prompts. Both select
    # abstract now that the frontend also shows it (click-to-expand on the
    # publication list). Ordered by recency, not citation count --
    # Publication has no stored citation count to rank by.
    cursor.execute(
        """
        SELECT Publication.title, Publication.abstract, Publication.publication_date
        FROM Publication
        JOIN ProfessorPublication ON ProfessorPublication.publication_id = Publication.id
        WHERE ProfessorPublication.professor_id = %s
        ORDER BY Publication.publication_date DESC NULLS LAST
        LIMIT %s;
        """,
        [professor_id, limit],
    )
    columns = [desc.name for desc in cursor.description]
    return [dict(zip(columns, row)) for row in cursor.fetchall()]


@app.get("/api/professors/{professor_id}")
@db.with_connection
def professor_detail(professor_id: int):
    connection = get_connection()
    cursor = connection.cursor()
    cursor.execute(
        """
        SELECT
            Professor.id,
            Professor.name AS professor_name,
            Professor.email,
            Professor.website,
            Professor.orcid,
            Professor.ai_summary,
            Professor.ai_summary_generated_at,
            Institution.name AS institution_name,
            Institution.website AS institution_website,
            Institution.city,
            Institution.state,
            Institution.country_code,
            Institution.carnegie_classification
        FROM Professor
        LEFT JOIN Institution ON Institution.id = Professor.institution_id
        WHERE Professor.id = %s;
        """,
        [professor_id],
    )
    row = cursor.fetchone()
    if row is None:
        cursor.close()
        raise HTTPException(status_code=404, detail="Professor not found")

    columns = [desc.name for desc in cursor.description]
    professor = dict(zip(columns, row))
    professor["topics"] = _fetch_professor_topics(cursor, professor_id)
    cursor.close()
    return professor


@app.post("/api/professors/{professor_id}/summary")
@db.with_connection
def professor_summary(professor_id: int):
    # get_professor_ai_summary returns None only when the professor row
    # itself doesn't exist -- a professor with no summary yet still comes
    # back as (None, None), which is what triggers generation below.
    cached = db.get_professor_ai_summary(professor_id)
    if cached is None:
        raise HTTPException(status_code=404, detail="Professor not found")

    summary, generated_at = cached
    if summary is not None:
        return {"summary": summary, "generated_at": generated_at, "cached": True}

    connection = get_connection()
    cursor = connection.cursor()
    cursor.execute(
        """
        SELECT Professor.name, Institution.name
        FROM Professor
        LEFT JOIN Institution ON Institution.id = Professor.institution_id
        WHERE Professor.id = %s;
        """,
        [professor_id],
    )
    name, institution_name = cursor.fetchone()
    topics = _fetch_professor_topics(cursor, professor_id, limit=8)
    publications = _fetch_recent_publications_with_abstracts(cursor, professor_id, limit=8)
    cursor.close()

    if not topics and not publications:
        # Nothing to ground a summary in -- generating one anyway risks
        # inventing detail about a real named academic. Absent beats
        # wrong; see CLAUDE.md / docs/ROADMAP.md Phase 5A.
        return {"summary": None, "generated_at": None, "cached": False, "reason": "insufficient_data"}

    try:
        summary_text = generate_summary(name, institution_name, topics, publications)
    except SummaryGenerationNotConfigured:
        raise HTTPException(status_code=503, detail="AI summaries are not configured yet.")
    except SummaryGenerationRefused:
        raise HTTPException(status_code=502, detail="Couldn't generate a summary for this professor.")

    db.update_professor_ai_summary(professor_id, summary_text)
    updated_summary, updated_generated_at = db.get_professor_ai_summary(professor_id)
    return {"summary": updated_summary, "generated_at": updated_generated_at, "cached": False}


@app.get("/api/professors/{professor_id}/publications")
@db.with_connection
def professor_publications(professor_id: int):
    connection = get_connection()
    cursor = connection.cursor()
    cursor.execute(
        """
        SELECT Publication.title, Publication.abstract, Publication.journal, Publication.publication_date,
               Publication.doi, Publication.url
        FROM Publication
        JOIN ProfessorPublication ON ProfessorPublication.publication_id = Publication.id
        WHERE ProfessorPublication.professor_id = %s
        ORDER BY Publication.publication_date DESC NULLS LAST;
        """,
        [professor_id],
    )
    columns = [desc.name for desc in cursor.description]
    rows = [dict(zip(columns, row)) for row in cursor.fetchall()]
    cursor.close()
    return {"publications": rows}


# Column order returned by db.get_student_profile() -- that function returns
# a raw row tuple (same convention as get_professor_ai_summary), so this is
# the one place that turns it into the dict shape backend/llm.py expects.
STUDENT_PROFILE_COLUMNS = [
    "user_id",
    "level",
    "school",
    "graduation_year",
    "coursework",
    "skills",
    "prior_experience",
    "looking_for",
]


@app.post("/api/professors/{professor_id}/cold-email")
@db.with_connection
def professor_cold_email(professor_id: int, user=Depends(current_user)):
    # user is the raw (id, email, email_verified, name, avatar_url) tuple
    # current_user returns -- same indexing convention as backend/auth.py.
    user_id, _email, _email_verified, user_name, _avatar_url = user
    profile_row = db.get_student_profile(user_id)
    if profile_row is None:
        # A draft with nothing to say about the student is worse than no
        # draft -- ask them to fill out a profile first rather than
        # generating a generic, unpersonalized email. See CLAUDE.md /
        # docs/ROADMAP.md Phase 5A: absent beats wrong.
        raise HTTPException(
            status_code=422,
            detail="Complete your student profile before generating an email draft.",
        )
    profile = dict(zip(STUDENT_PROFILE_COLUMNS, profile_row))

    connection = get_connection()
    cursor = connection.cursor()
    cursor.execute(
        """
        SELECT Professor.name, Institution.name
        FROM Professor
        LEFT JOIN Institution ON Institution.id = Professor.institution_id
        WHERE Professor.id = %s;
        """,
        [professor_id],
    )
    row = cursor.fetchone()
    if row is None:
        cursor.close()
        raise HTTPException(status_code=404, detail="Professor not found")
    professor_name, institution_name = row

    topics = _fetch_professor_topics(cursor, professor_id, limit=8)
    publications = _fetch_recent_publications_with_abstracts(cursor, professor_id, limit=5)
    cursor.close()

    if not topics and not publications:
        # Nothing to ground the professor half of the email in -- same
        # "absent beats wrong" call as the summary endpoint above.
        return {"draft": None, "reason": "insufficient_data"}

    try:
        draft_body = generate_cold_email(
            user_name, profile, professor_name, institution_name, topics, publications
        )
    except ColdEmailGenerationNotConfigured:
        raise HTTPException(status_code=503, detail="Email drafting is not configured yet.")
    except ColdEmailGenerationRefused:
        raise HTTPException(status_code=502, detail="Couldn't draft an email for this professor.")

    draft_id = db.insert_email_draft(user_id, professor_id, draft_body)
    return {"draft": draft_body, "draft_id": draft_id}


@app.get("/api/institutions")
@db.with_connection
def list_institutions(q: str | None = None, limit: int = Query(20, ge=1, le=100)):
    connection = get_connection()
    cursor = connection.cursor()
    if q:
        cursor.execute(
            "SELECT name FROM Institution WHERE name ILIKE %s ORDER BY name LIMIT %s;",
            [f"%{q}%", limit],
        )
    else:
        cursor.execute("SELECT name FROM Institution ORDER BY name LIMIT %s;", [limit])
    institutions = [row[0] for row in cursor.fetchall()]
    cursor.close()
    return {"institutions": institutions}


@app.get("/healthz")
@db.with_connection
def healthz():
    # Only returns 200 if a real query against the DB succeeds, so a
    # deploy platform restarts a container that's up but can't reach the
    # database, rather than leaving it serving broken responses. See
    # docs/ROADMAP.md Phase 6.1.
    connection = get_connection()
    cursor = connection.cursor()
    try:
        cursor.execute("SELECT 1;")
        cursor.fetchone()
    except Exception:
        raise HTTPException(status_code=503, detail="Database unavailable")
    finally:
        cursor.close()
    return {"status": "ok"}


frontend_dir = Path(__file__).resolve().parent.parent / "frontend"
app.mount("/", StaticFiles(directory=frontend_dir, html=True), name="frontend")
