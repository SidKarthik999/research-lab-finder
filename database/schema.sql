CREATE TABLE Institution (
    id SERIAL PRIMARY KEY,
    name TEXT NOT NULL UNIQUE,
    website TEXT,
    city TEXT,
    state TEXT,
    country TEXT
);

CREATE TABLE Department (
    id SERIAL PRIMARY KEY,
    name TEXT NOT NULL,
    institution_id INTEGER NOT NULL,

    FOREIGN KEY (institution_id)
        REFERENCES Institution(id)
);

CREATE TABLE Professor (
    id SERIAL PRIMARY KEY,
    name TEXT NOT NULL,
    email TEXT,
    ORCID TEXT UNIQUE,
    website TEXT,
    department_id INTEGER NOT NULL,

    FOREIGN KEY (department_id)
        REFERENCES Department(id)
);

CREATE TABLE Lab (
    id SERIAL PRIMARY KEY,
    name TEXT NOT NULL,
    website TEXT,
    description TEXT,
    city TEXT,
    state TEXT,
    country TEXT,
    department_id INTEGER NOT NULL,
    pi_professor_id INTEGER NOT NULL,
    FOREIGN KEY (department_id)
        REFERENCES Department(id),
    FOREIGN KEY (pi_professor_id)
        REFERENCES Professor(id)
);

CREATE TABLE Publication(
    id SERIAL PRIMARY KEY,
    title TEXT NOT NULL,
    abstract TEXT,
    publication_date DATE,
    journal TEXT,
    DOI TEXT UNIQUE,
    url TEXT
);

CREATE TABLE ResearchTopic (
    id SERIAL PRIMARY KEY,
    name TEXT NOT NULL UNIQUE
);

CREATE TABLE ProfessorPublication (
    professor_id INTEGER NOT NULL,
    publication_id INTEGER NOT NULL,
    PRIMARY KEY (professor_id, publication_id),
    FOREIGN KEY (professor_id)
        REFERENCES Professor(id),
    FOREIGN KEY (publication_id)
        REFERENCES Publication(id)
);

CREATE TABLE PublicationTopic (
    publication_id INTEGER NOT NULL,
    topic_id INTEGER NOT NULL,
    PRIMARY KEY (publication_id, topic_id),
    FOREIGN KEY (publication_id)
        REFERENCES Publication(id),
    FOREIGN KEY (topic_id)
        REFERENCES ResearchTopic(id)
);

CREATE TABLE LabResearchTopic (
    lab_id INTEGER NOT NULL,
    topic_id INTEGER NOT NULL,
    PRIMARY KEY (lab_id, topic_id),
    FOREIGN KEY (lab_id)
        REFERENCES Lab(id),
    FOREIGN KEY (topic_id)
        REFERENCES ResearchTopic(id)
);