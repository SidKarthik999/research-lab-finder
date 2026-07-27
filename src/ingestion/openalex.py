from dotenv import load_dotenv
import os
import pyalex
import pprint
from src.database import insert_institution

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

def ingest_institutions_from_file(filename):
    with open(filename, "r") as file:
        institutions = file.readlines()

    for institution_name in institutions:
        institution_name = institution_name.strip()

        if institution_name:
            insert_openalex_institution(institution_name)

ingest_institutions_from_file("data/institutions.txt")