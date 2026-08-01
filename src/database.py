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

def get_all_labs():
    connection = get_connection()
    cursor = connection.cursor()
    query = '''
    SELECT *
    FROM Lab
    '''
    cursor.execute(query)
    labs = cursor.fetchall()
    cursor.close()
    return labs

def get_labs_at_institution(institution_name):
    connection = get_connection()
    cursor = connection.cursor()
    query = '''
    SELECT Lab.name
    FROM Lab
    JOIN Department on Lab.department_id = Department.id
    JOIN Institution on Department.institution_id = Institution.id
    WHERE Institution.name = %s
    '''
    cursor.execute(query, (institution_name,))
    labs = cursor.fetchall()
    cursor.close()
    return labs

def get_labs_by_topic(topic_name):
    connection = get_connection()
    cursor = connection.cursor()
    query = '''
    SELECT Lab.name
    FROM Lab
    JOIN LabResearchTopic on Lab.id = LabResearchTopic.lab_id
    JOIN ResearchTopic on LabResearchTopic.topic_id = ResearchTopic.id
    WHERE ResearchTopic.name = %s
    '''
    cursor.execute(query, (topic_name,))
    labs = cursor.fetchall()
    cursor.close()
    return labs

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

def insert_research_topic(name, source=None):
    connection = get_connection()
    cursor = connection.cursor()
    query = '''
    INSERT INTO ResearchTopic (
        name,
        source
    )
    VALUES (%s, %s)
    ON CONFLICT (name)
    DO UPDATE SET
        updated_at = CURRENT_TIMESTAMP
    RETURNING id;
    '''
    cursor.execute(query,(name, source))
    topic_id = cursor.fetchone()[0]
    connection.commit()
    cursor.close()
    return topic_id

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

def insert_publication_topic(publication_id, topic_id):
    connection = get_connection()
    cursor = connection.cursor()
    query = '''
    INSERT INTO PublicationTopic (
        publication_id,
        topic_id
    )
    VALUES (%s, %s)
    ON CONFLICT (publication_id, topic_id)
    DO NOTHING;
    '''
    cursor.execute(query,(publication_id, topic_id))
    connection.commit()
    cursor.close()

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

def insert_department(name, institution_id, source=None):
    connection = get_connection()
    cursor = connection.cursor()
    query = '''
    INSERT INTO Department (
        name,
        institution_id,
        source
    )
    VALUES (%s, %s, %s)
    ON CONFLICT (name, institution_id)
    DO UPDATE SET
        updated_at = CURRENT_TIMESTAMP
    RETURNING id;
    '''
    cursor.execute(query,(name, institution_id, source))
    department_id = cursor.fetchone()[0]
    connection.commit()
    cursor.close()
    return department_id

def insert_lab(name, department_id=None, pi_professor_id=None, website=None, description=None, source=None):
    connection = get_connection()
    cursor = connection.cursor()
    query = '''
    INSERT INTO Lab (
        name,
        department_id,
        pi_professor_id,
        website,
        description,
        source
    )
    VALUES (%s, %s, %s, %s, %s, %s)
    ON CONFLICT (pi_professor_id)
    DO UPDATE SET
        website = COALESCE(EXCLUDED.website, Lab.website),
        description = COALESCE(EXCLUDED.description, Lab.description),
        updated_at = CURRENT_TIMESTAMP
    RETURNING id;
    '''
    cursor.execute(query,(name, department_id, pi_professor_id, website, description, source))
    lab_id = cursor.fetchone()[0]
    connection.commit()
    cursor.close()
    return lab_id

def update_lab_contact(pi_professor_id, name=None, website=None, description=None):
    connection = get_connection()
    cursor = connection.cursor()
    query = '''
    UPDATE Lab
    SET name = COALESCE(%s, name),
        website = COALESCE(%s, website),
        description = COALESCE(%s, description),
        updated_at = CURRENT_TIMESTAMP
    WHERE pi_professor_id = %s
    RETURNING id;
    '''
    cursor.execute(query,(name, website, description, pi_professor_id))
    row = cursor.fetchone()
    lab_id = row[0] if row else None
    connection.commit()
    cursor.close()
    return lab_id

def insert_professor_department(professor_id, department_id):
    connection = get_connection()
    cursor = connection.cursor()
    query = '''
    INSERT INTO ProfessorDepartment (
        professor_id,
        department_id
    )
    VALUES (%s, %s)
    ON CONFLICT (professor_id, department_id)
    DO NOTHING;
    '''
    cursor.execute(query,(professor_id, department_id))
    connection.commit()
    cursor.close()

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
    cursor.execute(query,(professor_id, lab_id))
    connection.commit()
    cursor.close()

def insert_lab_research_topic(lab_id, topic_id):
    connection = get_connection()
    cursor = connection.cursor()
    query = '''
    INSERT INTO LabResearchTopic (
        lab_id,
        topic_id
    )
    VALUES (%s, %s)
    ON CONFLICT (lab_id, topic_id)
    DO NOTHING;
    '''
    cursor.execute(query,(lab_id, topic_id))
    connection.commit()
    cursor.close()