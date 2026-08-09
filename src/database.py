import contextvars
import functools
import os

import psycopg
from psycopg.errors import UniqueViolation
from psycopg_pool import ConnectionPool

# DATABASE_URL is unset in local dev -- falls back to the same local
# peer/trust-auth connection this module always used. Production sets
# DATABASE_URL (see docs/ROADMAP.md Phase 6.1).
_DEFAULT_CONNINFO = "dbname=research_lab_finder user=siddanthkarthik"

_pool = None

# One checked-out connection per logical unit of work, not per thread
# forever -- the opposite of the old threading.local cache, which is
# exactly what let a hosted Postgres's dropped-idle-connection behavior go
# unnoticed against local Postgres. "Unit of work" here specifically means
# "one call to a function decorated with with_connection() below" (a route
# handler, or a Depends() callable like current_user), NOT "one HTTP
# request" -- verified empirically that FastAPI runs each sync dependency
# and the sync endpoint body as *separate* threadpool calls, each getting
# its own independently-copied contextvars.Context, so a contextvar set in
# one is invisible in the other even when the same OS thread happens to be
# reused. A single request-scoped release (e.g. from middleware, which runs
# in the async context that spawned those threaded calls) can't see what
# any of them checked out -- decorating each such function individually is
# what keeps checkout and release inside the same copied context.
# Ingestion scripts get correct behavior for free without decoration: each
# script is one plain Python process/thread with no threadpool involved, so
# the ambient context is never copied out from under them.
_current_connection = contextvars.ContextVar("_current_connection", default=None)


def init_pool():
    """Opens the pool. Called from backend/main.py's lifespan handler on
    startup; ingestion scripts and tests never call this directly -- they
    get a lazily-initialized pool from get_connection() below instead, since
    they have no lifespan handler to call it for them."""
    global _pool
    if _pool is not None:
        return
    conninfo = os.environ.get("DATABASE_URL", _DEFAULT_CONNINFO)
    _pool = ConnectionPool(
        conninfo,
        kwargs={"autocommit": True},
        min_size=1,
        max_size=10,
        check=ConnectionPool.check_connection,
        open=False,
    )
    _pool.open()


def close_pool():
    """Closes the pool. Called from backend/main.py's lifespan handler on
    shutdown."""
    global _pool
    if _pool is not None:
        _pool.close()
        _pool = None


def get_connection():
    connection = _current_connection.get()
    if connection is not None and not connection.closed:
        return connection

    init_pool()
    connection = _pool.getconn()
    _current_connection.set(connection)
    return connection


def release_connection():
    """Returns the current context's connection to the pool, if any. Called
    by with_connection() below after each decorated call, and at the end of
    every ingestion script (still exported as close_connection for those
    call sites -- the name stuck from before pooling, but the behavior now
    is "give it back to the pool", not "close the socket")."""
    connection = _current_connection.get()
    if connection is not None:
        _pool.putconn(connection)
        _current_connection.set(None)


# Old name, kept because every ingestion script's __main__ block already
# imports and calls this at the end of its run.
close_connection = release_connection


def with_connection(func):
    """Decorator for a route handler or FastAPI Depends() callable that
    touches the database: any connection checked out via get_connection()
    during this call is returned to the pool when the call finishes, success
    or error alike. See the _current_connection comment above for why this
    has to be per-function rather than per-request."""

    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        finally:
            release_connection()

    return wrapper

def get_all_institutions():
    connection = get_connection()
    cursor = connection.cursor()
    query = '''
    SELECT *
    FROM Institution
    '''
    cursor.execute(query)
    institutions = cursor.fetchall()
    cursor.close()
    return institutions

def insert_institution(name, website=None, city=None, state=None, country_code=None, openalex_id=None, ror_id=None, source=None):
    connection = get_connection()
    cursor = connection.cursor()
    query = '''
    INSERT INTO Institution (
        name,
        website,
        city,
        state,
        country_code,
        source,
        openalex_id,
        ror_id
    )
    VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
    ON CONFLICT (openalex_id)
    DO UPDATE SET
        updated_at = CURRENT_TIMESTAMP
    RETURNING id;
    '''
    cursor.execute(query,(name, website, city, state, country_code, source, openalex_id, ror_id))
    institution_id = cursor.fetchone()[0]
    connection.commit()
    cursor.close()
    return institution_id


def get_institutions_without_carnegie_classification():
    connection = get_connection()
    cursor = connection.cursor()
    query = '''
    SELECT id, name, city, state
    FROM Institution
    WHERE carnegie_classification IS NULL
    '''
    cursor.execute(query)
    institutions = cursor.fetchall()
    cursor.close()
    return institutions

def update_institution_carnegie_classification(institution_id, classification, unitid, match_method):
    connection = get_connection()
    cursor = connection.cursor()
    query = '''
    UPDATE Institution
    SET carnegie_classification = %s,
        carnegie_unitid = %s,
        carnegie_match_method = %s,
        updated_at = CURRENT_TIMESTAMP
    WHERE id = %s;
    '''
    cursor.execute(query, (classification, unitid, match_method, institution_id))
    connection.commit()
    cursor.close()

def insert_professor(name, email=None, orcid=None, website=None, institution_id=None, source=None, openalex_id=None):
    connection = get_connection()
    cursor = connection.cursor()
    query = '''
    INSERT INTO Professor (
        name,
        email,
        orcid,
        website,
        institution_id,
        openalex_id,
        source
    )
    VALUES (%s, %s, %s, %s, %s, %s, %s)
    ON CONFLICT (openalex_id)
    DO UPDATE SET
        name = COALESCE(EXCLUDED.name, Professor.name),
        website = COALESCE(EXCLUDED.website, Professor.website),
        email = COALESCE(EXCLUDED.email, Professor.email),
        institution_id = COALESCE(EXCLUDED.institution_id, Professor.institution_id),
        updated_at = CURRENT_TIMESTAMP
    RETURNING id;
    '''
    try:
        cursor.execute(query,(name, email, orcid, website, institution_id, openalex_id, source))
        professor_id = cursor.fetchone()[0]
    except UniqueViolation:
        cursor.close()
        return merge_professor_by_orcid(orcid, email, website, institution_id)

    connection.commit()
    cursor.close()
    return professor_id

def merge_professor_by_orcid(orcid, email=None, website=None, institution_id=None):
    connection = get_connection()
    cursor = connection.cursor()
    query = '''
    UPDATE Professor
    SET website = COALESCE(%s, website),
        email = COALESCE(%s, email),
        institution_id = COALESCE(%s, institution_id),
        updated_at = CURRENT_TIMESTAMP
    WHERE orcid = %s
    RETURNING id;
    '''
    cursor.execute(query,(website, email, institution_id, orcid))
    row = cursor.fetchone()
    professor_id = row[0] if row else None
    connection.commit()
    cursor.close()
    return professor_id

def get_all_professors():
    connection = get_connection()
    cursor = connection.cursor()
    query = '''
    SELECT *
    FROM Professor
    '''
    cursor.execute(query)
    professors = cursor.fetchall()
    cursor.close()
    return professors

def get_professors_with_orcid():
    connection = get_connection()
    cursor = connection.cursor()
    query = '''
    SELECT Professor.id, Professor.name, Professor.orcid, Institution.name, Institution.country_code
    FROM Professor
    JOIN Institution ON Institution.id = Professor.institution_id
    WHERE Professor.orcid IS NOT NULL
    '''
    cursor.execute(query)
    professors = cursor.fetchall()
    cursor.close()
    return professors

def update_professor_name(professor_id, name):
    connection = get_connection()
    cursor = connection.cursor()
    query = '''
    UPDATE Professor
    SET name = %s,
        updated_at = CURRENT_TIMESTAMP
    WHERE id = %s;
    '''
    cursor.execute(query, (name, professor_id))
    connection.commit()
    cursor.close()

def update_professor_email(professor_id, email):
    connection = get_connection()
    cursor = connection.cursor()
    query = '''
    UPDATE Professor
    SET email = %s,
        updated_at = CURRENT_TIMESTAMP
    WHERE id = %s;
    '''
    cursor.execute(query, (email, professor_id))
    connection.commit()
    cursor.close()

def update_professor_website(professor_id, website):
    connection = get_connection()
    cursor = connection.cursor()
    query = '''
    UPDATE Professor
    SET website = %s,
        updated_at = CURRENT_TIMESTAMP
    WHERE id = %s;
    '''
    cursor.execute(query, (website, professor_id))
    connection.commit()
    cursor.close()

def clear_professor_orcid(professor_id):
    connection = get_connection()
    cursor = connection.cursor()
    query = '''
    UPDATE Professor
    SET orcid = NULL,
        updated_at = CURRENT_TIMESTAMP
    WHERE id = %s;
    '''
    cursor.execute(query, (professor_id,))
    connection.commit()
    cursor.close()

def get_professors_for_publication_ingestion():
    connection = get_connection()
    cursor = connection.cursor()
    query = '''
    SELECT id, name, openalex_id
    FROM Professor
    WHERE openalex_id IS NOT NULL
    '''
    cursor.execute(query)
    professors = cursor.fetchall()
    cursor.close()
    return professors

def get_professors_without_publications():
    connection = get_connection()
    cursor = connection.cursor()
    query = '''
    SELECT id, name, openalex_id
    FROM Professor
    WHERE openalex_id IS NOT NULL
    AND NOT EXISTS (
        SELECT 1 FROM ProfessorPublication WHERE ProfessorPublication.professor_id = Professor.id
    )
    '''
    cursor.execute(query)
    professors = cursor.fetchall()
    cursor.close()
    return professors

def get_professors_without_topics():
    connection = get_connection()
    cursor = connection.cursor()
    query = '''
    SELECT id, name, openalex_id
    FROM Professor
    WHERE openalex_id IS NOT NULL
    AND NOT EXISTS (
        SELECT 1 FROM ProfessorTopic WHERE ProfessorTopic.professor_id = Professor.id
    )
    '''
    cursor.execute(query)
    professors = cursor.fetchall()
    cursor.close()
    return professors

def insert_publication(title, abstract=None, publication_date=None, journal=None, doi=None, url=None, source=None, openalex_id=None):
    connection = get_connection()
    cursor = connection.cursor()
    query = '''
    INSERT INTO Publication (
        title,
        abstract,
        publication_date,
        journal,
        doi,
        url,
        openalex_id,
        source
    )
    VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
    ON CONFLICT (openalex_id)
    DO UPDATE SET
        updated_at = CURRENT_TIMESTAMP
    RETURNING id;
    '''
    try:
        cursor.execute(query,(title, abstract, publication_date, journal, doi, url, openalex_id, source))
        publication_id = cursor.fetchone()[0]
    except UniqueViolation:
        cursor.close()
        return merge_publication_by_doi(doi, title, abstract, publication_date, journal, url)

    connection.commit()
    cursor.close()
    return publication_id

def merge_publication_by_doi(doi, title=None, abstract=None, publication_date=None, journal=None, url=None):
    connection = get_connection()
    cursor = connection.cursor()
    query = '''
    UPDATE Publication
    SET title = COALESCE(%s, title),
        abstract = COALESCE(%s, abstract),
        publication_date = COALESCE(%s, publication_date),
        journal = COALESCE(%s, journal),
        url = COALESCE(%s, url),
        updated_at = CURRENT_TIMESTAMP
    WHERE doi = %s
    RETURNING id;
    '''
    cursor.execute(query,(title, abstract, publication_date, journal, url, doi))
    row = cursor.fetchone()
    publication_id = row[0] if row else None
    connection.commit()
    cursor.close()
    return publication_id

def insert_professor_publication(professor_id, publication_id):
    connection = get_connection()
    cursor = connection.cursor()
    query = '''
    INSERT INTO ProfessorPublication (
        professor_id,
        publication_id
    )
    VALUES (%s, %s)
    ON CONFLICT (professor_id, publication_id)
    DO NOTHING;
    '''
    cursor.execute(query,(professor_id, publication_id))
    connection.commit()
    cursor.close()

def get_institution_by_name(name):
    connection = get_connection()
    cursor = connection.cursor()
    query = '''
    SELECT id FROM Institution
    WHERE name = %s;
    '''
    cursor.execute(query, (name,))
    row = cursor.fetchone()
    cursor.close()
    return row[0] if row else None

def get_professors_by_institution(institution_id):
    connection = get_connection()
    cursor = connection.cursor()
    query = '''
    SELECT id, name
    FROM Professor
    WHERE institution_id = %s
    '''
    cursor.execute(query, (institution_id,))
    professors = cursor.fetchall()
    cursor.close()
    return professors

def insert_professor_stub(name, institution_id, source=None):
    connection = get_connection()
    cursor = connection.cursor()
    select_query = '''
    SELECT id FROM Professor
    WHERE institution_id = %s AND name = %s;
    '''
    cursor.execute(select_query, (institution_id, name))
    row = cursor.fetchone()
    if row:
        cursor.close()
        return row[0]

    insert_query = '''
    INSERT INTO Professor (
        name,
        institution_id,
        source
    )
    VALUES (%s, %s, %s)
    RETURNING id;
    '''
    cursor.execute(insert_query, (name, institution_id, source))
    professor_id = cursor.fetchone()[0]
    connection.commit()
    cursor.close()
    return professor_id

def insert_lab(name, institution_id, department=None, website=None, source=None):
    connection = get_connection()
    cursor = connection.cursor()
    query = '''
    INSERT INTO Lab (
        name,
        institution_id,
        department,
        website,
        source
    )
    VALUES (%s, %s, %s, %s, %s)
    ON CONFLICT (institution_id, name)
    DO UPDATE SET
        department = COALESCE(EXCLUDED.department, Lab.department),
        website = COALESCE(EXCLUDED.website, Lab.website),
        updated_at = CURRENT_TIMESTAMP
    RETURNING id;
    '''
    cursor.execute(query, (name, institution_id, department, website, source))
    lab_id = cursor.fetchone()[0]
    connection.commit()
    cursor.close()
    return lab_id

def insert_professor_lab(professor_id, lab_id):
    connection = get_connection()
    cursor = connection.cursor()
    query = '''
    INSERT INTO ProfessorLab (
        professor_id,
        lab_id
    )
    VALUES (%s, %s)
    ON CONFLICT (professor_id, lab_id)
    DO NOTHING;
    '''
    cursor.execute(query, (professor_id, lab_id))
    connection.commit()
    cursor.close()

def insert_research_topic(openalex_id, name, subfield=None, field=None, domain=None, source=None):
    connection = get_connection()
    cursor = connection.cursor()
    query = '''
    INSERT INTO ResearchTopic (
        openalex_id,
        name,
        subfield,
        field,
        domain,
        source
    )
    VALUES (%s, %s, %s, %s, %s, %s)
    ON CONFLICT (openalex_id)
    DO UPDATE SET
        name = EXCLUDED.name,
        subfield = EXCLUDED.subfield,
        field = EXCLUDED.field,
        domain = EXCLUDED.domain,
        updated_at = CURRENT_TIMESTAMP
    RETURNING id;
    '''
    cursor.execute(query, (openalex_id, name, subfield, field, domain, source))
    topic_id = cursor.fetchone()[0]
    connection.commit()
    cursor.close()
    return topic_id

def insert_professor_topic(professor_id, topic_id, works_count=None):
    connection = get_connection()
    cursor = connection.cursor()
    query = '''
    INSERT INTO ProfessorTopic (
        professor_id,
        topic_id,
        works_count
    )
    VALUES (%s, %s, %s)
    ON CONFLICT (professor_id, topic_id)
    DO UPDATE SET
        works_count = EXCLUDED.works_count;
    '''
    cursor.execute(query, (professor_id, topic_id, works_count))
    connection.commit()
    cursor.close()

def get_publications_for_professor(professor_id):
    connection = get_connection()
    cursor = connection.cursor()
    query = '''
    SELECT Publication.title, Publication.journal, Publication.publication_date,
           Publication.doi, Publication.url
    FROM Publication
    JOIN ProfessorPublication ON ProfessorPublication.publication_id = Publication.id
    WHERE ProfessorPublication.professor_id = %s
    ORDER BY Publication.publication_date DESC NULLS LAST;
    '''
    cursor.execute(query, (professor_id,))
    publications = cursor.fetchall()
    cursor.close()
    return publications

def get_user_by_email(email):
    connection = get_connection()
    cursor = connection.cursor()
    query = '''
    SELECT id, email, email_verified, name, avatar_url
    FROM AppUser
    WHERE email = %s;
    '''
    cursor.execute(query, (email,))
    row = cursor.fetchone()
    cursor.close()
    return row

def get_user_by_id(user_id):
    connection = get_connection()
    cursor = connection.cursor()
    query = '''
    SELECT id, email, email_verified, name, avatar_url
    FROM AppUser
    WHERE id = %s;
    '''
    cursor.execute(query, (user_id,))
    row = cursor.fetchone()
    cursor.close()
    return row

def insert_user(email, name=None, avatar_url=None, email_verified=False):
    connection = get_connection()
    cursor = connection.cursor()
    query = '''
    INSERT INTO AppUser (
        email,
        name,
        avatar_url,
        email_verified
    )
    VALUES (%s, %s, %s, %s)
    ON CONFLICT (email)
    DO UPDATE SET
        name = COALESCE(EXCLUDED.name, AppUser.name),
        avatar_url = COALESCE(EXCLUDED.avatar_url, AppUser.avatar_url),
        email_verified = AppUser.email_verified OR EXCLUDED.email_verified,
        updated_at = CURRENT_TIMESTAMP
    RETURNING id;
    '''
    cursor.execute(query, (email, name, avatar_url, email_verified))
    user_id = cursor.fetchone()[0]
    connection.commit()
    cursor.close()
    return user_id

def update_user_name(user_id, name):
    connection = get_connection()
    cursor = connection.cursor()
    query = '''
    UPDATE AppUser
    SET name = %s,
        updated_at = CURRENT_TIMESTAMP
    WHERE id = %s;
    '''
    cursor.execute(query, (name, user_id))
    connection.commit()
    cursor.close()

def mark_user_email_verified(user_id):
    connection = get_connection()
    cursor = connection.cursor()
    query = '''
    UPDATE AppUser
    SET email_verified = TRUE,
        updated_at = CURRENT_TIMESTAMP
    WHERE id = %s;
    '''
    cursor.execute(query, (user_id,))
    connection.commit()
    cursor.close()

def get_auth_identity(provider, provider_user_id):
    connection = get_connection()
    cursor = connection.cursor()
    query = '''
    SELECT id, user_id, provider, provider_user_id, password_hash
    FROM AuthIdentity
    WHERE provider = %s AND provider_user_id = %s;
    '''
    cursor.execute(query, (provider, provider_user_id))
    row = cursor.fetchone()
    cursor.close()
    return row

def get_identities_for_user(user_id):
    connection = get_connection()
    cursor = connection.cursor()
    query = '''
    SELECT provider, provider_user_id, created_at
    FROM AuthIdentity
    WHERE user_id = %s;
    '''
    cursor.execute(query, (user_id,))
    identities = cursor.fetchall()
    cursor.close()
    return identities

def insert_auth_identity(user_id, provider, provider_user_id, password_hash=None):
    connection = get_connection()
    cursor = connection.cursor()
    # On conflict, only bump updated_at -- never reassign user_id or touch
    # password_hash here. Google sign-in calls this on every login, so it
    # must be idempotent, but silently repointing an existing identity at a
    # different user_id (or clobbering a password hash) on a routine login
    # call would be an account-takeover-shaped bug. Password changes go
    # through update_identity_password instead.
    query = '''
    INSERT INTO AuthIdentity (
        user_id,
        provider,
        provider_user_id,
        password_hash
    )
    VALUES (%s, %s, %s, %s)
    ON CONFLICT (provider, provider_user_id)
    DO UPDATE SET
        updated_at = CURRENT_TIMESTAMP
    RETURNING id;
    '''
    cursor.execute(query, (user_id, provider, provider_user_id, password_hash))
    identity_id = cursor.fetchone()[0]
    connection.commit()
    cursor.close()
    return identity_id

def update_identity_password(identity_id, password_hash):
    connection = get_connection()
    cursor = connection.cursor()
    query = '''
    UPDATE AuthIdentity
    SET password_hash = %s,
        updated_at = CURRENT_TIMESTAMP
    WHERE id = %s;
    '''
    cursor.execute(query, (password_hash, identity_id))
    connection.commit()
    cursor.close()

def get_student_profile(user_id):
    connection = get_connection()
    cursor = connection.cursor()
    query = '''
    SELECT user_id, level, school, graduation_year, coursework, skills, prior_experience, looking_for
    FROM StudentProfile
    WHERE user_id = %s;
    '''
    cursor.execute(query, (user_id,))
    row = cursor.fetchone()
    cursor.close()
    return row

def upsert_student_profile(user_id, level=None, school=None, graduation_year=None, coursework=None, skills=None, prior_experience=None, looking_for=None):
    connection = get_connection()
    cursor = connection.cursor()
    # Full replace (EXCLUDED, not COALESCE) on conflict -- unlike the
    # OpenAlex-ingest upserts above, this is the student directly editing
    # their own form, so a field they clear should actually clear rather
    # than keep the old stored value.
    query = '''
    INSERT INTO StudentProfile (
        user_id,
        level,
        school,
        graduation_year,
        coursework,
        skills,
        prior_experience,
        looking_for
    )
    VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
    ON CONFLICT (user_id)
    DO UPDATE SET
        level = EXCLUDED.level,
        school = EXCLUDED.school,
        graduation_year = EXCLUDED.graduation_year,
        coursework = EXCLUDED.coursework,
        skills = EXCLUDED.skills,
        prior_experience = EXCLUDED.prior_experience,
        looking_for = EXCLUDED.looking_for,
        updated_at = CURRENT_TIMESTAMP
    RETURNING user_id;
    '''
    cursor.execute(query, (user_id, level, school, graduation_year, coursework, skills, prior_experience, looking_for))
    returned_id = cursor.fetchone()[0]
    connection.commit()
    cursor.close()
    return returned_id

def insert_email_draft(user_id, professor_id, body):
    connection = get_connection()
    cursor = connection.cursor()
    query = '''
    INSERT INTO EmailDraft (
        user_id,
        professor_id,
        body
    )
    VALUES (%s, %s, %s)
    RETURNING id;
    '''
    cursor.execute(query, (user_id, professor_id, body))
    draft_id = cursor.fetchone()[0]
    connection.commit()
    cursor.close()
    return draft_id

def get_email_drafts_for_professor(user_id, professor_id):
    connection = get_connection()
    cursor = connection.cursor()
    query = '''
    SELECT id, body, created_at
    FROM EmailDraft
    WHERE user_id = %s AND professor_id = %s
    ORDER BY created_at DESC;
    '''
    cursor.execute(query, (user_id, professor_id))
    drafts = cursor.fetchall()
    cursor.close()
    return drafts

def update_email_draft(draft_id, user_id, professor_id, body):
    # user_id and professor_id are both in the WHERE clause, not just the
    # primary key -- draft_id alone came from the client, so this is what
    # actually stops one student from editing another's draft (or a draft
    # under the wrong professor) by guessing/tampering with an id.
    connection = get_connection()
    cursor = connection.cursor()
    query = '''
    UPDATE EmailDraft
    SET body = %s
    WHERE id = %s AND user_id = %s AND professor_id = %s
    RETURNING id;
    '''
    cursor.execute(query, (body, draft_id, user_id, professor_id))
    updated = cursor.fetchone() is not None
    connection.commit()
    cursor.close()
    return updated

def insert_bookmark(user_id, professor_id):
    connection = get_connection()
    cursor = connection.cursor()
    query = '''
    INSERT INTO Bookmark (user_id, professor_id)
    VALUES (%s, %s)
    ON CONFLICT (user_id, professor_id) DO NOTHING
    RETURNING id;
    '''
    cursor.execute(query, (user_id, professor_id))
    row = cursor.fetchone()
    connection.commit()
    cursor.close()
    return row[0] if row else None

def insert_professor_flag(professor_id, user_id, reasons, details):
    connection = get_connection()
    cursor = connection.cursor()
    query = '''
    INSERT INTO ProfessorFlag (professor_id, user_id, reasons, details)
    VALUES (%s, %s, %s, %s)
    RETURNING id;
    '''
    cursor.execute(query, (professor_id, user_id, reasons, details))
    flag_id = cursor.fetchone()[0]
    connection.commit()
    cursor.close()
    return flag_id

def delete_bookmark(user_id, professor_id):
    connection = get_connection()
    cursor = connection.cursor()
    cursor.execute('DELETE FROM Bookmark WHERE user_id = %s AND professor_id = %s;', (user_id, professor_id))
    connection.commit()
    cursor.close()

def is_professor_bookmarked(user_id, professor_id):
    connection = get_connection()
    cursor = connection.cursor()
    cursor.execute('SELECT 1 FROM Bookmark WHERE user_id = %s AND professor_id = %s;', (user_id, professor_id))
    bookmarked = cursor.fetchone() is not None
    cursor.close()
    return bookmarked

def get_bookmarks_for_user(user_id):
    connection = get_connection()
    cursor = connection.cursor()
    # latest_draft is scoped to this same user_id via the LATERAL join's own
    # WHERE clause (not just professor_id) -- two different students who
    # bookmarked the same professor must each see only their own draft.
    query = '''
    SELECT
        Bookmark.id,
        Bookmark.created_at,
        Professor.id,
        Professor.name,
        Institution.name,
        Institution.city,
        Institution.state,
        Institution.country_code,
        latest_draft.body,
        latest_draft.created_at
    FROM Bookmark
    JOIN Professor ON Professor.id = Bookmark.professor_id
    LEFT JOIN Institution ON Institution.id = Professor.institution_id
    LEFT JOIN LATERAL (
        SELECT body, created_at
        FROM EmailDraft
        WHERE EmailDraft.professor_id = Professor.id AND EmailDraft.user_id = Bookmark.user_id
        ORDER BY created_at DESC
        LIMIT 1
    ) latest_draft ON TRUE
    WHERE Bookmark.user_id = %s
    ORDER BY Bookmark.created_at DESC;
    '''
    cursor.execute(query, (user_id,))
    bookmarks = cursor.fetchall()
    cursor.close()
    return bookmarks

def get_professor_ai_summary(professor_id):
    connection = get_connection()
    cursor = connection.cursor()
    query = '''
    SELECT ai_summary, ai_summary_generated_at
    FROM Professor
    WHERE id = %s;
    '''
    cursor.execute(query, (professor_id,))
    row = cursor.fetchone()
    cursor.close()
    return row

def update_professor_ai_summary(professor_id, summary):
    connection = get_connection()
    cursor = connection.cursor()
    query = '''
    UPDATE Professor
    SET ai_summary = %s,
        ai_summary_generated_at = CURRENT_TIMESTAMP,
        updated_at = CURRENT_TIMESTAMP
    WHERE id = %s;
    '''
    cursor.execute(query, (summary, professor_id))
    connection.commit()
    cursor.close()

def count_llm_usage_today(user_id, kind):
    # CURRENT_DATE is UTC-midnight-bounded (Postgres server timezone,
    # unconfigured here) -- a coarse day boundary is fine for a spend
    # guard, doesn't need to track each student's own timezone.
    connection = get_connection()
    cursor = connection.cursor()
    query = '''
    SELECT COUNT(*)
    FROM LlmUsage
    WHERE user_id = %s AND kind = %s AND created_at >= CURRENT_DATE;
    '''
    cursor.execute(query, (user_id, kind))
    count = cursor.fetchone()[0]
    cursor.close()
    return count

def insert_llm_usage(user_id, kind):
    connection = get_connection()
    cursor = connection.cursor()
    query = '''
    INSERT INTO LlmUsage (user_id, kind) VALUES (%s, %s);
    '''
    cursor.execute(query, (user_id, kind))
    connection.commit()
    cursor.close()
