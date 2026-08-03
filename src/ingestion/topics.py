"""Backfill ResearchTopic/ProfessorTopic for professors already ingested via
openalex.py.

Fetches each professor's own OpenAlex Author record and reads its `topics`
field directly (`pyalex.Authors()[openalex_author_id]`), rather than
inferring subject matter from Works affiliated with an institution -- see
CLAUDE.md for why that approach was replaced. Author.topics is derived from
that author's own works, so there's no attribution risk here, the same
safe pattern publications.py already uses.

Author.topics doesn't include a normalized score; each topic instead carries
a `count` (how many of the author's own works are tagged with it), already
ordered most-relevant-first. That count is stored as ProfessorTopic.works_count.

Run from the repo root: python -m src.ingestion.topics
"""

import os

import pyalex
from dotenv import load_dotenv

from src.database import (
    close_connection,
    get_professors_for_publication_ingestion,
    insert_professor_topic,
    insert_research_topic,
)

load_dotenv()

pyalex.config.api_key = os.getenv("OPENALEX_API_KEY")


def get_author_topics(openalex_author_id):
    author = pyalex.Authors()[openalex_author_id]
    return author.get("topics") or []


def insert_openalex_topic(topic):
    subfield = (topic.get("subfield") or {}).get("display_name")
    field = (topic.get("field") or {}).get("display_name")
    domain = (topic.get("domain") or {}).get("display_name")
    return insert_research_topic(
        openalex_id=topic["id"],
        name=topic["display_name"],
        subfield=subfield,
        field=field,
        domain=domain,
        source="OpenAlex",
    )


def insert_topics_for_professor(professor_id, openalex_author_id):
    topics = get_author_topics(openalex_author_id)
    for topic in topics:
        topic_id = insert_openalex_topic(topic)
        insert_professor_topic(professor_id, topic_id, works_count=topic.get("count"))
    return len(topics)


def insert_topics_from_professors(professors):
    professors_processed = 0
    for professor_id, name, openalex_id in professors:
        try:
            topic_count = insert_topics_for_professor(professor_id, openalex_id)
            print(f"Inserted {topic_count} topics for {name}")
            professors_processed += 1

        except Exception as e:
            print(f"Failed {name}: {e}")

    return professors_processed


if __name__ == "__main__":
    professors = get_professors_for_publication_ingestion()

    insert_topics_from_professors(professors)

    close_connection()
