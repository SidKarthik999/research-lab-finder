"""FastAPI search backend for Research Lab Finder.

Serves the search API under /api/* and the static frontend (../frontend)
at /. No LLM involved yet -- pure SQL filtering over the OpenAlex-sourced
Postgres data. See CLAUDE.md for the data model.

Institution, Professor, Publication, and (as of Phase 1) ResearchTopic
exist. Lab is also live but not yet surfaced here.

Run from the repo root: uvicorn backend.main:app --reload
"""

from pathlib import Path

from fastapi import FastAPI, Query
from fastapi.staticfiles import StaticFiles

from src.database import get_connection

app = FastAPI(title="Research Lab Finder API")


def build_search_query(
    q=None,
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
    """
    conditions = []
    params = []

    if q:
        like = f"%{q}%"
        conditions.append(
            """(
                Professor.name ILIKE %s
                OR Institution.name ILIKE %s
                OR EXISTS (
                    SELECT 1 FROM ProfessorTopic pt
                    JOIN ResearchTopic rt ON rt.id = pt.topic_id
                    WHERE pt.professor_id = Professor.id
                      AND (rt.name ILIKE %s OR rt.field ILIKE %s OR rt.subfield ILIKE %s)
                )
                OR EXISTS (
                    SELECT 1 FROM ProfessorPublication pp
                    JOIN Publication pub ON pub.id = pp.publication_id
                    WHERE pp.professor_id = Professor.id
                      AND pub.search_vector @@ websearch_to_tsquery('english', %s)
                )
            )"""
        )
        params.extend([like, like, like, like, like, q])
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
    #    matched (via q, topic=, or field=) -- how central that subject
    #    actually is to this professor's own work.
    #  - text_rank: how well their publications match the free-text query.
    #  - last_publication_date: recency, as the final tie-breaker, so
    #    inactive/retired professors don't rank above active ones.
    rank_conditions = []
    rank_params = []
    if q:
        like = f"%{q}%"
        rank_conditions.append("(rt.name ILIKE %s OR rt.field ILIKE %s OR rt.subfield ILIKE %s)")
        rank_params.extend([like, like, like])
    if topic:
        rank_conditions.append("(rt.name ILIKE %s OR rt.field ILIKE %s OR rt.subfield ILIKE %s)")
        like = f"%{topic}%"
        rank_params.extend([like, like, like])
    if field:
        rank_conditions.append("rt.field ILIKE %s")
        rank_params.append(f"%{field}%")
    topic_rank_where = f"AND ({' OR '.join(rank_conditions)})" if rank_conditions else "AND FALSE"
    # Used to prioritize matching topics in the "topics" chip list below, so
    # a professor surfaced by a topic/field/q match shows *that* topic first
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

    all_params = [*rank_params, q, q, *rank_params, *params, limit, offset]

    return query, all_params


@app.get("/api/search")
def search_professors(
    q: str | None = Query(
        None,
        description="Keyword across professor/institution names, research topics, and publication text",
    ),
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
        q=q,
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
