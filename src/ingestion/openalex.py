from dotenv import load_dotenv
import os
import pyalex
import pprint
from src.database import insert_institution, insert_professor

load_dotenv()

pyalex.config.api_key = os.getenv("OPENALEX_API_KEY")


def search_institution(institution_name):
    results = pyalex.Institutions().search(institution_name).get()
    if results:
        return results[0]
    return None

def insert_openalex_institution(institution_name):
    institution = search_institution(institution_name=institution_name)
    if institution is None:
        return None
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

def insert_institutions_from_file(filename):
    with open(filename, "r") as file:
        institutions = file.readlines()

    for institution_name in institutions:
        institution_name = institution_name.strip()

        if not institution_name:
            continue
        try:
            institution_id = insert_openalex_institution(institution_name)
            print(f"Inserted {institution_name}: {institution_id}")

        except Exception as e:
            print(f"Failed {institution_name}: {e}")

def get_openalex_works(institution_name):
    institution = search_institution(institution_name)

    if institution is None:
        return []

    institution_id = institution["id"]
    works = (
        pyalex.Works()
        .filter(institutions={"id": institution_id})
        .get(per_page=25)
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

def insert_professors_from_institution(institution_name):
    works = get_openalex_works(institution_name)
    professors_inserted = 0
    for work in works:
        for author in work['authorships']:
            professor_id = insert_openalex_professor(author)
            print(f"Inserted {author['author']['display_name']}: {professor_id}")
            professors_inserted += 1

    return professors_inserted

if __name__  == "__main__":
    insert_openalex_institution("Carnegie Mellon University")
    count = insert_professors_from_institution("Carnegie Mellon University")
    print(f"Inserted {count} professors")