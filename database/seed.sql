-- Institutions

INSERT INTO Institution (name, website, city, state, country, source) VALUES
('Massachusetts Institute of Technology', 'https://www.mit.edu/', 'Cambridge', 'MA', 'USA', 'manual'),
('Stanford University', 'https://www.stanford.edu/', 'Stanford', 'CA', 'USA', 'manual'),
('Carnegie Mellon University', 'https://www.cmu.edu/', 'Pittsburgh', 'PA', 'USA', 'manual');


-- Departments

INSERT INTO Department (name, institution_id, source) VALUES
(
    'Electrical Engineering and Computer Science',
    (SELECT id FROM Institution WHERE name='Massachusetts Institute of Technology'),
    'manual'
),
(
    'Computer Science',
    (SELECT id FROM Institution WHERE name='Stanford University'),
    'manual'
),
(
    'School of Computer Science',
    (SELECT id FROM Institution WHERE name='Carnegie Mellon University'),
    'manual'
);


-- Professors

INSERT INTO Professor (name, email, ORCID, website, source) VALUES
('Regina Barzilay', 'regina@mit.edu', '0000-0001-0001-0001', 'https://www.csail.mit.edu/', 'manual'),
('Fei-Fei Li', 'fei-fei@stanford.edu', '0000-0002-0002-0002', 'https://ai.stanford.edu/', 'manual'),
('Tom Mitchell', 'tom.mitchell@cmu.edu', '0000-0003-0003-0003', 'https://www.cs.cmu.edu/', 'manual');


-- Professor Department relationships

INSERT INTO ProfessorDepartment (professor_id, department_id) VALUES
(
    (SELECT id FROM Professor WHERE name='Regina Barzilay'),
    (SELECT id FROM Department WHERE name='Electrical Engineering and Computer Science')
),
(
    (SELECT id FROM Professor WHERE name='Fei-Fei Li'),
    (SELECT id FROM Department WHERE name='Computer Science')
),
(
    (SELECT id FROM Professor WHERE name='Tom Mitchell'),
    (SELECT id FROM Department WHERE name='School of Computer Science')
);


-- Labs

INSERT INTO Lab
(name, website, description, city, state, country, department_id, pi_professor_id, source)
VALUES

(
    'MIT Machine Learning for Healthcare Lab',
    'https://example.com/mit-healthcare',
    'Develops machine learning methods for healthcare applications.',
    'Cambridge',
    'MA',
    'USA',
    (SELECT id FROM Department WHERE name='Electrical Engineering and Computer Science'),
    (SELECT id FROM Professor WHERE name='Regina Barzilay'),
    'manual'
),

(
    'Stanford Artificial Intelligence Laboratory',
    'https://example.com/stanford-ai',
    'Research lab focused on artificial intelligence and computer vision.',
    'Stanford',
    'CA',
    'USA',
    (SELECT id FROM Department WHERE name='Computer Science'),
    (SELECT id FROM Professor WHERE name='Fei-Fei Li'),
    'manual'
),

(
    'CMU Machine Learning Department',
    'https://example.com/cmu-ml',
    'Research in machine learning algorithms and applications.',
    'Pittsburgh',
    'PA',
    'USA',
    (SELECT id FROM Department WHERE name='School of Computer Science'),
    (SELECT id FROM Professor WHERE name='Tom Mitchell'),
    'manual'
);


-- Professor Lab relationships

INSERT INTO ProfessorLab (professor_id, lab_id) VALUES
(
    (SELECT id FROM Professor WHERE name='Regina Barzilay'),
    (SELECT id FROM Lab WHERE name='MIT Machine Learning for Healthcare Lab')
),
(
    (SELECT id FROM Professor WHERE name='Fei-Fei Li'),
    (SELECT id FROM Lab WHERE name='Stanford Artificial Intelligence Laboratory')
),
(
    (SELECT id FROM Professor WHERE name='Tom Mitchell'),
    (SELECT id FROM Lab WHERE name='CMU Machine Learning Department')
);


-- Publications

INSERT INTO Publication
(title, abstract, publication_date, journal, DOI, url, source)
VALUES

(
    'Machine Learning for Biomedical Data Analysis',
    'Methods for applying machine learning techniques to biomedical datasets.',
    '2024-01-15',
    'Nature Machine Intelligence',
    '10.1000/mlbio001',
    'https://example.com/paper1',
    'manual'
),

(
    'Deep Learning for Computer Vision Applications',
    'A study of deep neural networks for visual recognition.',
    '2023-06-20',
    'IEEE Transactions on Pattern Analysis',
    '10.1000/cv002',
    'https://example.com/paper2',
    'manual'
),

(
    'Statistical Learning Theory and Applications',
    'Foundations and applications of machine learning.',
    '2022-03-10',
    'Journal of Machine Learning Research',
    '10.1000/ml003',
    'https://example.com/paper3',
    'manual'
);


-- Professor Publication relationships

INSERT INTO ProfessorPublication (professor_id, publication_id) VALUES
(
    (SELECT id FROM Professor WHERE name='Regina Barzilay'),
    (SELECT id FROM Publication WHERE DOI='10.1000/mlbio001')
),

(
    (SELECT id FROM Professor WHERE name='Fei-Fei Li'),
    (SELECT id FROM Publication WHERE DOI='10.1000/cv002')
),

(
    (SELECT id FROM Professor WHERE name='Tom Mitchell'),
    (SELECT id FROM Publication WHERE DOI='10.1000/ml003')
);


-- Research Topics

INSERT INTO ResearchTopic (name, source) VALUES
('Machine Learning', 'manual'),
('Artificial Intelligence', 'manual'),
('Computer Vision', 'manual'),
('Biomedical AI', 'manual');


-- Lab Research Topics

INSERT INTO LabResearchTopic (lab_id, topic_id) VALUES

(
    (SELECT id FROM Lab WHERE name='MIT Machine Learning for Healthcare Lab'),
    (SELECT id FROM ResearchTopic WHERE name='Biomedical AI')
),

(
    (SELECT id FROM Lab WHERE name='MIT Machine Learning for Healthcare Lab'),
    (SELECT id FROM ResearchTopic WHERE name='Machine Learning')
),

(
    (SELECT id FROM Lab WHERE name='Stanford Artificial Intelligence Laboratory'),
    (SELECT id FROM ResearchTopic WHERE name='Computer Vision')
),

(
    (SELECT id FROM Lab WHERE name='CMU Machine Learning Department'),
    (SELECT id FROM ResearchTopic WHERE name='Machine Learning')
);


-- Publication Topics

INSERT INTO PublicationTopic (publication_id, topic_id) VALUES

(
    (SELECT id FROM Publication WHERE DOI='10.1000/mlbio001'),
    (SELECT id FROM ResearchTopic WHERE name='Biomedical AI')
),

(
    (SELECT id FROM Publication WHERE DOI='10.1000/cv002'),
    (SELECT id FROM ResearchTopic WHERE name='Computer Vision')
),

(
    (SELECT id FROM Publication WHERE DOI='10.1000/ml003'),
    (SELECT id FROM ResearchTopic WHERE name='Machine Learning')
);