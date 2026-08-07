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
from pathlib import Path

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Query
from fastapi.staticfiles import StaticFiles
from starlette.middleware.sessions import SessionMiddleware

from backend.auth import router as auth_router
from backend.llm import SummaryGenerationNotConfigured, SummaryGenerationRefused, generate_summary
from src import database as db
from src.database import get_connection

load_dotenv()

app = FastAPI(title="Research Lab Finder API")

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


def build_search_query(
    name=None,
    text=None,
    institution=None,
    city=None,
    state=None,
    country=None,
    topic=None,
    field=None,
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
def search_professors(
    name: str | None = Query(None, description="Match against the professor's own name"),
    text: str | None = Query(None, description="Free-text search over publication titles and abstracts"),
    institution: str | None = None,
    city: str | None = None,
    state: str | None = None,
    country: str | None = None,
    topic: str | None = Query(None, description="Filter by research topic name"),
    field: str | None = Query(None, description="Filter by research field, e.g. 'Physics and Astronomy'"),
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


@app.get("/api/topics")
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
    # is for the reading-list display and doesn't need abstract; this one
    # feeds the summary prompt and does. Ordered by recency, not citation
    # count -- Publication has no stored citation count to rank by.
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
            Institution.country_code
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
def professor_publications(professor_id: int):
    connection = get_connection()
    cursor = connection.cursor()
    cursor.execute(
        """
        SELECT Publication.title, Publication.journal, Publication.publication_date,
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


@app.get("/api/institutions")
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


frontend_dir = Path(__file__).resolve().parent.parent / "frontend"
app.mount("/", StaticFiles(directory=frontend_dir, html=True), name="frontend")
