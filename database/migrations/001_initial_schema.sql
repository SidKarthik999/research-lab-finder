-- Baseline schema, captured as of the 2026-08-01 rebuild (Institution,
-- Professor, Publication, ProfessorPublication, Lab, ProfessorLab).
--
-- Uses IF NOT EXISTS because this migration is also the one that registers
-- the already-live production schema into schema_migrations -- applying it
-- against a database that already has these tables must be a safe no-op,
-- not a failure.

CREATE TABLE IF NOT EXISTS Institution (
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

CREATE TABLE IF NOT EXISTS Professor (
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

CREATE TABLE IF NOT EXISTS Publication (
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

CREATE TABLE IF NOT EXISTS ProfessorPublication (
    professor_id INTEGER NOT NULL,
    publication_id INTEGER NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    PRIMARY KEY (professor_id, publication_id),

    FOREIGN KEY (professor_id)
        REFERENCES Professor(id),

    FOREIGN KEY (publication_id)
        REFERENCES Publication(id)
);

CREATE TABLE IF NOT EXISTS Lab (
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

CREATE TABLE IF NOT EXISTS ProfessorLab (
    professor_id INTEGER NOT NULL,
    lab_id INTEGER NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    PRIMARY KEY (professor_id, lab_id),

    FOREIGN KEY (professor_id)
        REFERENCES Professor(id),

    FOREIGN KEY (lab_id)
        REFERENCES Lab(id)
);
