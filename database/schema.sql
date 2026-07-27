CREATE TABLE Institution (
    id SERIAL PRIMARY KEY,
    name TEXT NOT NULL UNIQUE,
    website TEXT,
    city TEXT,
    state TEXT,
    country_code TEXT,
    source TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    openalex_id TEXT UNIQUE,
    ror_id TEXT UNIQUE
);

CREATE TABLE Department (
    id SERIAL PRIMARY KEY,
    name TEXT NOT NULL,
    institution_id INTEGER NOT NULL,
    source TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    UNIQUE(name, institution_id),

    FOREIGN KEY (institution_id)
        REFERENCES Institution(id)
);

CREATE TABLE Professor (
    id SERIAL PRIMARY KEY,
    name TEXT NOT NULL,
    email TEXT,
    ORCID TEXT UNIQUE,
    website TEXT,
    source TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    openalex_id TEXT UNIQUE
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
    pi_professor_id INTEGER,
    source TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    FOREIGN KEY (department_id)
        REFERENCES Department(id),

    FOREIGN KEY (pi_professor_id)
        REFERENCES Professor(id)
);

CREATE TABLE Publication (
    id SERIAL PRIMARY KEY,
    title TEXT NOT NULL,
    abstract TEXT,
    publication_date DATE,
    journal TEXT,
    doi TEXT UNIQUE,
    url TEXT,
    source TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    openalex_id TEXT UNIQUE
);

CREATE TABLE ResearchTopic (
    id SERIAL PRIMARY KEY,
    name TEXT NOT NULL UNIQUE,
    source TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE ProfessorPublication (
    professor_id INTEGER NOT NULL,
    publication_id INTEGER NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    PRIMARY KEY (professor_id, publication_id),

    FOREIGN KEY (professor_id)
        REFERENCES Professor(id),

    FOREIGN KEY (publication_id)
        REFERENCES Publication(id)
);

CREATE TABLE PublicationTopic (
    publication_id INTEGER NOT NULL,
    topic_id INTEGER NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    PRIMARY KEY (publication_id, topic_id),

    FOREIGN KEY (publication_id)
        REFERENCES Publication(id),

    FOREIGN KEY (topic_id)
        REFERENCES ResearchTopic(id)
);

CREATE TABLE LabResearchTopic (
    lab_id INTEGER NOT NULL,
    topic_id INTEGER NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    PRIMARY KEY (lab_id, topic_id),

    FOREIGN KEY (lab_id)
        REFERENCES Lab(id),

    FOREIGN KEY (topic_id)
        REFERENCES ResearchTopic(id)
);

CREATE TABLE ProfessorDepartment (
    professor_id INTEGER NOT NULL,
    department_id INTEGER NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    PRIMARY KEY (professor_id, department_id),

    FOREIGN KEY (professor_id)
        REFERENCES Professor(id),

    FOREIGN KEY (department_id)
        REFERENCES Department(id)
);

CREATE TABLE ProfessorLab (
    professor_id INTEGER NOT NULL,
    lab_id INTEGER NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    PRIMARY KEY (professor_id, lab_id),

    FOREIGN KEY (professor_id)
        REFERENCES Professor(id),

    FOREIGN KEY (lab_id)
        REFERENCES Lab(id)
);