"""Claude-generated professor summaries (Phase 5A).

Split the same way as the auth modules (backend/tokens.py,
backend/google_auth.py): build_summary_prompt() and its formatting
helpers are pure -- no network, no DB -- so prompt assembly is testable
without an API key, the same reasoning that keeps build_search_query()
in backend/main.py separate from the route handler that executes it.
generate_summary() is the actual Claude API call and isn't unit tested,
mirroring the OpenAlex fetch functions in src/ingestion/.

Every summary is generated only from data already in this database
(name, institution, topics, the professor's own publication titles and
abstracts) -- never from the model's own knowledge of the person. This
is a real named academic who did not sign up for this; a confidently
wrong paragraph about them is the worst failure mode this feature can
produce. See CLAUDE.md / docs/ROADMAP.md Phase 5A.
"""

import os

import anthropic

MODEL = "claude-opus-5"
MAX_ABSTRACT_CHARS = 600

SYSTEM_PROMPT = """\
You write short, factual summaries of academic researchers for a directory \
that helps students find research opportunities. You are given only a \
professor's name, institution, research topics, and a handful of their own \
publication titles and abstracts -- nothing else.

Write one paragraph (3-5 sentences) describing who they are and what they \
work on, grounded strictly in the information given.

Rules:
- Never state anything not directly supported by the provided data. If the \
data is thin, write a shorter, more general paragraph rather than inventing \
detail.
- Do not guess at awards, titles (e.g. "chair", "director"), years of \
experience, or personal details that aren't given.
- Do not editorialize about how good, prestigious, or important the work is.
- Write in third person, in plain language a high school or college student \
would understand -- avoid jargon where a simpler term works, and briefly \
explain technical terms you must use.
- Do not mention that you are an AI or that this was generated from limited \
data -- the surrounding interface already discloses that.\
"""


class SummaryGenerationNotConfigured(Exception):
    """ANTHROPIC_API_KEY isn't set -- distinct from a failed generation so
    the route handler can return a clean "not configured" response instead
    of surfacing whatever error the SDK happens to raise."""


class SummaryGenerationRefused(Exception):
    """The model declined to generate a summary, or returned no text."""


def _format_topics(topics):
    if not topics:
        return "(no listed research topics)"
    return "\n".join(f"- {topic['name']}" for topic in topics)


def _format_publications(publications):
    if not publications:
        return "(no publications on file)"
    lines = []
    for pub in publications:
        title = pub.get("title") or "(untitled)"
        publication_date = pub.get("publication_date")
        year = publication_date.year if publication_date else None
        lines.append(f"- {title}" + (f" ({year})" if year else ""))
        abstract = pub.get("abstract")
        if abstract:
            if len(abstract) > MAX_ABSTRACT_CHARS:
                abstract = abstract[:MAX_ABSTRACT_CHARS].rstrip() + "..."
            lines.append(f"  Abstract: {abstract}")
    return "\n".join(lines)


def build_summary_prompt(name, institution_name, topics, publications):
    return (
        f"Professor: {name}\n"
        f"Institution: {institution_name or '(unknown)'}\n\n"
        "Research topics (from their own publication record, most prominent first):\n"
        f"{_format_topics(topics)}\n\n"
        "Recent publications (title and abstract where available):\n"
        f"{_format_publications(publications)}\n\n"
        "Write the summary paragraph now."
    )


def generate_summary(name, institution_name, topics, publications):
    if not os.environ.get("ANTHROPIC_API_KEY"):
        raise SummaryGenerationNotConfigured()

    client = anthropic.Anthropic()
    prompt = build_summary_prompt(name, institution_name, topics, publications)
    response = client.messages.create(
        model=MODEL,
        max_tokens=500,
        system=SYSTEM_PROMPT,
        output_config={"effort": "low"},
        messages=[{"role": "user", "content": prompt}],
    )

    if response.stop_reason == "refusal":
        raise SummaryGenerationRefused()

    text = "".join(block.text for block in response.content if block.type == "text").strip()
    if not text:
        raise SummaryGenerationRefused()
    return text
