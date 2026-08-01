-- Barebones-plus-publications-plus-labs MVP schema.
--
-- ResearchTopic, Department, and their junction tables (LabResearchTopic,
-- ProfessorDepartment, PublicationTopic) are still intentionally shelved --
-- the prior Works-based ingestion produced misattributed labs and synthetic
-- placeholder rows. Publication came back first (2026-08-01) because it
-- hangs safely off already-attributed Professor rows (see
-- src/ingestion/publications.py). Lab came back second (2026-08-01) sourced
-- from university lab-directory pages rather than OpenAlex Works, since
-- OpenAlex has no lab entity -- see src/ingestion/labs.py and CLAUDE.md.

DROP TABLE IF EXISTS
    ProfessorLab,
    LabResearchTopic,
    PublicationTopic,
    ProfessorPublication,
    ProfessorDepartment,
    Lab,
    Publication,
    ResearchTopic,
    Department
    CASCADE;

DROP TABLE IF EXISTS Professor CASCADE;
DROP TABLE IF EXISTS Institution CASCADE;

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

CREATE TABLE Professor (
    id SERIAL PRIMARY KEY,
    name TEXT NOT NULL,
    email TEXT,
    ORCID TEXT UNIQUE,
    website TEXT,
    institution_id INTEGER,
    source TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    openalex_id TEXT UNIQUE,

    FOREIGN KEY (institution_id)
        REFERENCES Institution(id)
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

CREATE TABLE Lab (
    id SERIAL PRIMARY KEY,
    name TEXT NOT NULL,
    institution_id INTEGER,
    department TEXT,
    website TEXT,
    source TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    FOREIGN KEY (institution_id)
        REFERENCES Institution(id),

    UNIQUE (institution_id, name)
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
