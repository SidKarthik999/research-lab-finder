import psycopg
from psycopg.errors import UniqueViolation
import threading

_local = threading.local()

def get_connection():
    connection = getattr(_local, "connection", None)
    if connection is None or connection.closed:
        connection = psycopg.connect(
            dbname='research_lab_finder',
            user='siddanthkarthik',
            autocommit=True
        )
        _local.connection = connection
    return connection

def close_connection():
    connection = getattr(_local, "connection", None)
    if connection is not None and not connection.closed:
        connection.close()
    _local.connection = None

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
