from dotenv import load_dotenv
import os
import pyalex
import pprint
from src.database import (
    insert_institution,
    insert_professor,
    insert_publication,
    insert_research_topic,
    insert_professor_publication,
    insert_publication_topic,
    insert_lab,
    insert_professor_lab,
    insert_lab_research_topic,
    close_connection,
)

load_dotenv()

pyalex.config.api_key = os.getenv("OPENALEX_API_KEY")


def search_institution(institution_name):
    results = pyalex.Institutions().search(institution_name).get()
    if results:
        return results[0]
    return None

def get_top_us_institutions(limit=100):
    institutions = (
        pyalex.Institutions()
        .filter(country_code="US", type="education")
        .sort(works_count="desc")
        .get(per_page=limit)
    )
    return [institution["display_name"] for institution in institutions]

def insert_openalex_institution(institution):
    institution_id = insert_institution(
        name = institution['display_name'],
        website = institution.get('homepage_url'),
        city = institution['geo'].get('city'),
        state = institution['geo'].get('region'),
        country_code = institution['geo'].get('country_code'),
        openalex_id = institution['id'],
        ror_id = institution['ids'].get('ror'),
        source = "OpenAlex"
    )
    return institution_id

def get_openalex_works(openalex_institution_id):
    works = (
        pyalex.Works()
        .filter(institutions={"id": openalex_institution_id})
        .get(per_page=200)
    )
    return works

def insert_openalex_professor(author):
    professor_id = insert_professor(
        name=author['author']['display_name'],
        orcid=author['author']['orcid'],
        openalex_id=author['author']['id'],
        source="OpenAlex"
    )
    return professor_id

def insert_openalex_publication(work):
    primary_location = work.get('primary_location') or {}
    source_info = primary_location.get('source') or {}
    abstract_inverted_index = work.get('abstract_inverted_index')
    publication_id = insert_publication(
        title=work.get('display_name'),
        abstract=reconstruct_abstract(abstract_inverted_index) if abstract_inverted_index else None,
        publication_date=work.get('publication_date'),
        journal=source_info.get('display_name'),
        doi=work['ids'].get('doi'),
        url=primary_location.get('landing_page_url'),
        openalex_id=work['id'],
        source="OpenAlex"
    )
    return publication_id

def insert_openalex_topic(topic):
    topic_id = insert_research_topic(
        name=topic['display_name'],
        source="OpenAlex"
    )
    return topic_id

def insert_openalex_lab(professor_id, professor_name):
    lab_id = insert_lab(
        name=f"{professor_name} Lab",
        pi_professor_id=professor_id,
        source="OpenAlex-derived"
    )
    insert_professor_lab(professor_id, lab_id)
    return lab_id

def insert_publications_from_institution(works):
    publications_inserted = 0
    for work in works:
        try:
            publication_id = insert_openalex_publication(work)
            print(f"Inserted {work['display_name']}: {publication_id}")
            publications_inserted += 1

        except Exception as e:
            print(f"Failed {work['display_name']}: {e}")
            continue

        for author in work['authorships']:
            try:
                professor_id = insert_openalex_professor(author)
                insert_professor_publication(professor_id, publication_id)

                lab_id = insert_openalex_lab(professor_id, author['author']['display_name'])

                for topic in work.get('topics', []):
                    insert_lab_research_topic(lab_id, insert_openalex_topic(topic))

            except Exception as e:
                print(f"Failed {author['author']['display_name']}: {e}")

        for topic in work.get('topics', []):
            try:
                topic_id = insert_openalex_topic(topic)
                insert_publication_topic(publication_id, topic_id)

            except Exception as e:
                print(f"Failed {topic['display_name']}: {e}")

    return publications_inserted

def ingest_institution(institution_name):
    institution = search_institution(institution_name)
    if institution is None:
        print(f"Failed {institution_name}: not found in OpenAlex")
        return None

    institution_id = insert_openalex_institution(institution)
    print(f"Inserted {institution_name}: {institution_id}")

    works = get_openalex_works(institution["id"])
    insert_publications_from_institution(works)

    return institution_id

def reconstruct_abstract(abstract_inverted_index):
    max_position = max(
        position
        for positions in abstract_inverted_index.values()
        for position in positions
    )
    abstract_words = [""] * (max_position + 1)
    for word, positions in abstract_inverted_index.items():
        for position in positions:
            abstract_words[position] = word

    return " ".join(abstract_words)

if __name__  == "__main__":
    institution_names = get_top_us_institutions(100)

    for institution_name in institution_names:
        try:
            ingest_institution(institution_name)

        except Exception as e:
            print(f"Failed {institution_name}: {e}")

    close_connection()