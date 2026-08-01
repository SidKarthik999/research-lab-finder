"""FastAPI search backend for Research Lab Finder.

Serves the search API under /api/* and the static frontend (../frontend)
at /. No LLM involved yet -- pure SQL filtering over the OpenAlex-sourced
Postgres data. See CLAUDE.md for the data model.

Barebones MVP: Institution, Professor, and Publication exist. Lab/
ResearchTopic are still shelved for a future phase (see CLAUDE.md).

Run from the repo root: uvicorn backend.main:app --reload
"""

from pathlib import Path

from fastapi import FastAPI, Query
from fastapi.staticfiles import StaticFiles

from src.database import get_connection

app = FastAPI(title="Research Lab Finder API")


@app.get("/api/search")
def search_professors(
    q: str | None = Query(None, description="Keyword across professor and institution names"),
    institution: str | None = None,
    city: str | None = None,
    state: str | None = None,
    country: str | None = None,
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
):
    conditions = []
    params = []

    if q:
        conditions.append("(Professor.name ILIKE %s OR Institution.name ILIKE %s)")
        like = f"%{q}%"
        params.extend([like, like])
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

    where_clause = f"WHERE {' AND '.join(conditions)}" if conditions else ""
    offset = (page - 1) * limit

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
        Institution.country_code
    FROM Professor
    LEFT JOIN Institution ON Institution.id = Professor.institution_id
    {where_clause}
    ORDER BY Professor.name
    LIMIT %s OFFSET %s;
    """

    connection = get_connection()
    cursor = connection.cursor()
    cursor.execute(query, [*params, limit, offset])
    columns = [desc.name for desc in cursor.description]
    rows = [dict(zip(columns, row)) for row in cursor.fetchall()]
    cursor.close()
    return {"results": rows, "page": page, "limit": limit}


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
