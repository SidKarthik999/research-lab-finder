import psycopg
def get_connection():
    connection = psycopg.connect(
        dbname='research_lab_finder',
        user='siddanthkarthik'
    )
    return connection

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
    connection.close()
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
    connection.close()
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
    connection.close()
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
    connection.close()
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
    connection.close()
    return institution_id


def insert_professor(name, email=None, orcid=None, website=None, source=None, openalex_id=None):
    connection = get_connection()
    cursor = connection.cursor()
    query = '''
    INSERT INTO Professor (
        name,
        email,
        orcid,
        website,
        openalex_id,
        source
    )
    VALUES (%s, %s, %s, %s, %s, %s)
    ON CONFLICT (openalex_id)
    DO UPDATE SET
        updated_at = CURRENT_TIMESTAMP
    RETURNING id;
    '''
    cursor.execute(query,(name, email, orcid, website, openalex_id, source))
    professor_id = cursor.fetchone()[0]
    connection.commit()
    cursor.close()
    connection.close()
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
    cursor.execute(query,(title, abstract, publication_date, journal, doi, url, openalex_id, source))
    publication_id = cursor.fetchone()[0]
    connection.commit()
    cursor.close()
    connection.close()
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
    connection.close()
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
    connection.close()

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
    connection.close()

