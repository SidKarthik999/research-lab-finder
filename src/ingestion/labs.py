"""Attach Lab rows to Professors, sourced from university lab-directory pages
rather than OpenAlex (OpenAlex has no lab entity at all -- see CLAUDE.md).

Unlike openalex.py/publications.py, there is no API to page through here: lab
directories live on arbitrary department/school web pages with no common
structure, and a meaningful share of institution domains flat-out block
automated fetches (umich.edu returned 403 on every subdomain tried during the
pilot). For now, page-fetching and structured extraction is done by hand
(Claude Code fetching + reading each directory page) rather than wired into
this script -- lab_entries below is that manually-extracted data, passed
through the same insert/match/stub-creation logic a future automated version
would use.

Matching a directory's PI name against an existing Professor row is
surname-based, not full fuzzy matching: directory pages often give only a
surname ("Ermon") or "Firstname Lastname" with no middle initials, so an
exact-name match would almost always miss. A surname match combined with a
first-initial check (when a given name is present) is precise enough here
because it's scoped to one institution's professor list at a time.

Most PI names will *not* match an existing Professor row: professors were
only ingested up to the top 50 by works-count per institution (see
get_professors_at_institution in openalex.py), which skews heavily toward
the most-cited/medical fields. A lab directory for, say, an ECE or CS
department pulls names from a completely different slice of faculty. This
is expected and is the point -- unmatched PIs become new stub Professor
rows (source="Lab Directory", no openalex_id), growing the roster beyond
what OpenAlex's works-count ranking surfaced.

Run from the repo root: python -m src.ingestion.labs
"""

import re

from src.database import (
    close_connection,
    get_institution_by_name,
    get_professors_by_institution,
    insert_lab,
    insert_professor_lab,
    insert_professor_stub,
)


def surname(name):
    tokens = re.findall(r"[A-Za-z'-]+", name)
    return tokens[-1].lower() if tokens else None


def match_professor(pi_name, professors):
    """professors is a list of (id, name) tuples for one institution. Returns
    a professor_id on an unambiguous surname (+ first-initial, if given) match,
    else None.
    """
    pi_tokens = re.findall(r"[A-Za-z'-]+", pi_name)
    if not pi_tokens:
        return None

    pi_surname = pi_tokens[-1].lower()
    pi_initial = pi_tokens[0][0].lower() if len(pi_tokens) > 1 else None

    candidates = []
    for professor_id, professor_name in professors:
        if surname(professor_name) != pi_surname:
            continue
        if pi_initial:
            professor_tokens = re.findall(r"[A-Za-z'-]+", professor_name)
            if professor_tokens and professor_tokens[0][0].lower() != pi_initial:
                continue
        candidates.append(professor_id)

    if len(candidates) == 1:
        return candidates[0]
    return None  # no match, or ambiguous (multiple same-surname professors)


def ingest_labs_for_institution(institution_name, lab_entries, department=None):
    """lab_entries: list of dicts with keys 'name' (lab name, required),
    'pi' (PI name, optional), 'url' (lab website, optional),
    'department' (overrides the department= default, optional).
    """
    institution_id = get_institution_by_name(institution_name)
    if institution_id is None:
        raise ValueError(f"Unknown institution: {institution_name}")

    professors = list(get_professors_by_institution(institution_id))

    inserted_labs = 0
    matched = 0
    stubbed = 0

    for entry in lab_entries:
        try:
            lab_id = insert_lab(
                entry["name"],
                institution_id,
                department=entry.get("department", department),
                website=entry.get("url"),
                source="Lab Directory",
            )
            inserted_labs += 1

            pi_name = entry.get("pi")
            if not pi_name:
                continue

            professor_id = match_professor(pi_name, professors)
            if professor_id is not None:
                matched += 1
            else:
                professor_id = insert_professor_stub(pi_name, institution_id, source="Lab Directory")
                professors.append((professor_id, pi_name))
                stubbed += 1

            insert_professor_lab(professor_id, lab_id)
        except Exception as e:
            print(f"Failed to insert lab {entry.get('name')!r}: {e}")

    return inserted_labs, matched, stubbed


# Manually extracted pilot data (see module docstring). Stanford and Cornell
# were the two institutions whose directory pages were actually reachable;
# every umich.edu subdomain tried returned 403.
STANFORD_AI_LAB = [
    {"name": "Stanford Natural Language Processing (NLP) Group", "pi": "Chris Manning", "url": "https://nlp.stanford.edu/", "department": "Computer Science"},
    {"name": "Stanford Vision and Learning Lab (SVL)", "pi": "Fei-Fei Li", "url": "http://svl.stanford.edu/", "department": "Computer Science"},
    {"name": "Stanford Statistical Machine Learning (statsml) Group", "pi": "Percy Liang", "url": "http://statsml.stanford.edu/", "department": "Computer Science"},
    {"name": "Dror Lab", "pi": "Ron Dror", "url": "https://drorlab.stanford.edu/", "department": "Computer Science"},
    {"name": "Bejerano Lab", "pi": "Gill Bejerano", "url": "http://bejerano.stanford.edu/", "department": "Computer Science"},
    {"name": "Ermon Group", "pi": "Stefano Ermon", "url": "https://cs.stanford.edu/~ermon/website/", "department": "Computer Science"},
    {"name": "Leonidas Guibas Lab", "pi": "Leonidas Guibas", "url": "https://geometry.stanford.edu/", "department": "Computer Science"},
    {"name": "Stanford Robotics Lab", "pi": "Oussama Khatib", "url": "https://cs.stanford.edu/groups/manips/", "department": "Computer Science"},
    {"name": "Interactive Perception and Robot Learning Lab", "pi": "Jeannette Bohg", "url": "http://iprl.stanford.edu/", "department": "Computer Science"},
    {"name": "Intelligent and Interactive Autonomous Systems Group (ILIAD)", "pi": "Dorsa Sadigh", "url": "http://iliad.stanford.edu/", "department": "Computer Science"},
    {"name": "PhysBAM", "pi": "Ron Fedkiw", "url": "http://physbam.stanford.edu/", "department": "Computer Science"},
    {"name": "Stanford Logic Group", "pi": "Michael Genesereth", "url": "http://logic.stanford.edu/", "department": "Computer Science"},
    {"name": "Computation and Cognition Lab", "pi": "Noah D. Goodman", "url": "https://cocolab.stanford.edu/", "department": "Computer Science"},
    {"name": "NeuroAILab", "pi": "Daniel Yamins", "url": "https://neuroailab.stanford.edu/", "department": "Computer Science"},
    {"name": "Salisbury Robotics Lab", "pi": "K. Salisbury", "url": "https://web.stanford.edu/group/sailsbury_robotx/cgi-bin/salisbury_lab/", "department": "Computer Science"},
    {"name": "Stanford Intelligent Systems Laboratory", "pi": "Mykel Kochenderfer", "url": "https://web.stanford.edu/group/sisl/cgi-bin/wordpress/", "department": "Computer Science"},
    {"name": "Stanford Machine Learning Group", "pi": "Andrew Ng", "url": "https://stanfordmlgroup.github.io/", "department": "Computer Science"},
    {"name": "Autonomous Systems Lab", "pi": "Marco Pavone", "url": "http://asl.stanford.edu/", "department": "Computer Science"},
    {"name": "Christopher Ré Lab", "pi": "Christopher Ré", "url": "https://cs.stanford.edu/~chrismre/", "department": "Computer Science"},
    {"name": "The Movement Lab", "pi": "Kayvon Liu", "url": "https://tml.stanford.edu", "department": "Computer Science"},
    {"name": "SNAP Group", "pi": "Jure Leskovec", "url": "http://snap.stanford.edu/", "department": "Computer Science"},
    {"name": "Intelligence through Robotic Interaction at Scale Lab", "pi": "Chelsea Finn", "url": "https://irislab.stanford.edu/", "department": "Computer Science"},
]

CORNELL_ECE = [
    {"name": "Abdelfattah Research Group", "pi": "Mohsaied Abdelfattah", "url": "https://www.mohsaied.com/", "department": "Electrical and Computer Engineering"},
    {"name": "High Frequency Power Electronics Group", "pi": "Afridi", "url": "https://afridi.ece.cornell.edu/", "department": "Electrical and Computer Engineering"},
    {"name": "Alian Research Group", "pi": "Alian", "url": "https://arg.csl.cornell.edu/", "department": "Electrical and Computer Engineering"},
    {"name": "Apsel Lab", "pi": "Alyssa Apsel", "url": "https://apsellab.ece.cornell.edu/", "department": "Electrical and Computer Engineering"},
    {"name": "Quantum-Field & Integrated-Optics", "pi": "Bernard", "url": "https://bernard.ece.cornell.edu/", "department": "Electrical and Computer Engineering"},
    {"name": "Versatile Electronic Systems Lab (VESL)", "pi": None, "url": "https://vesl.ece.cornell.edu/", "department": "Electrical and Computer Engineering"},
    {"name": "Cornell-University of Bologna Institute for Vehicle Intelligence (Veho)", "pi": None, "url": "https://veho.mae.cornell.edu/", "department": "Electrical and Computer Engineering"},
    {"name": "Laboratory for Intelligent Systems and Controls (LISC)", "pi": None, "url": "https://lisc.mae.cornell.edu/wordpress/", "department": "Electrical and Computer Engineering"},
    {"name": "Integrated Quantum-Classical Micro-Systems (IQCs) Lab", "pi": "Ibrahim", "url": "https://sites.coecis.cornell.edu/ibrahim/", "department": "Electrical and Computer Engineering"},
    {"name": "Jena-Xing Laboratory", "pi": None, "url": "https://jena-xing.engineering.cornell.edu/", "department": "Electrical and Computer Engineering"},
    {"name": "Edwin Kan Group", "pi": "Edwin Kan", "url": "https://kan.ece.cornell.edu/", "department": "Electrical and Computer Engineering"},
    {"name": "Cornell Statistical Signal Processing Laboratory", "pi": None, "url": "https://ssplab.ece.cornell.edu/", "department": "Electrical and Computer Engineering"},
    {"name": "Cornell SonicMEMS Lab", "pi": None, "url": "https://sonicmems.ece.cornell.edu/", "department": "Electrical and Computer Engineering"},
    {"name": "Photonics and Quantum Electronics Group", "pi": "Mehta", "url": "https://sites.coecis.cornell.edu/mehta/", "department": "Electrical and Computer Engineering"},
    {"name": "Molnar Group", "pi": "Alyosha Molnar", "url": "https://molnargroup.ece.cornell.edu/", "department": "Electrical and Computer Engineering"},
    {"name": "Monticone Research Group", "pi": "Monticone", "url": "https://monticone.ece.cornell.edu/", "department": "Electrical and Computer Engineering"},
    {"name": "Collective Embodied Intelligence Lab", "pi": None, "url": "https://cei.ece.cornell.edu/", "department": "Electrical and Computer Engineering"},
    {"name": "Semiconductor Optoelectronics Group", "pi": "Rana", "url": "https://people.ece.cornell.edu/rana/", "department": "Electrical and Computer Engineering"},
    {"name": "Vision and Image Analysis Group (VIA)", "pi": None, "url": "https://www.via.cornell.edu/", "department": "Electrical and Computer Engineering"},
    {"name": "Sabuncu Lab", "pi": "Mert Sabuncu", "url": "https://sabuncu.engineering.cornell.edu/", "department": "Electrical and Computer Engineering"},
    {"name": "Seo Research Group", "pi": "Seo", "url": "https://seo.ece.cornell.edu/", "department": "Electrical and Computer Engineering"},
    {"name": "Zhang Research Group", "pi": "Zhang", "url": "https://zhang.ece.cornell.edu/", "department": "Electrical and Computer Engineering"},
    {"name": "Qing Zhao Group", "pi": "Qing Zhao", "url": "https://zhao.ece.cornell.edu/research/", "department": "Electrical and Computer Engineering"},
]


if __name__ == "__main__":
    for institution_name, lab_entries in [
        ("Stanford University", STANFORD_AI_LAB),
        ("Cornell University", CORNELL_ECE),
    ]:
        inserted, matched, stubbed = ingest_labs_for_institution(institution_name, lab_entries)
        print(f"{institution_name}: inserted {inserted} lab(s), matched {matched} existing professor(s), created {stubbed} stub professor(s)")

    close_connection()
