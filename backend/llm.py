"""GPT-generated professor summaries (Phase 5A).

Split the same way as the auth modules (backend/tokens.py,
backend/google_auth.py): build_summary_prompt() and its formatting
helpers are pure -- no network, no DB -- so prompt assembly is testable
without an API key, the same reasoning that keeps build_search_query()
in backend/main.py separate from the route handler that executes it.
generate_summary() is the actual OpenAI Responses API call and isn't
unit tested, mirroring the OpenAlex fetch functions in src/ingestion/.

Uses gpt-5.4-nano: this task is synthesis from provided facts, not
multi-step reasoning, so the cheapest current-generation tier is the
right fit -- reasoning effort is explicitly set to "none" rather than
left at whatever the SDK defaults to, since there's nothing here worth
deliberating over. (Originally built against Claude Opus 5; swapped
providers without touching anything below build_summary_prompt().)

Every summary is generated only from data already in this database
(name, institution, topics, the professor's own publication titles and
abstracts) -- never from the model's own knowledge of the person. This
is a real named academic who did not sign up for this; a confidently
wrong paragraph about them is the worst failure mode this feature can
produce. See CLAUDE.md / docs/ROADMAP.md Phase 5A.
"""

import os

import openai

MODEL = "gpt-5.4-nano"
MAX_ABSTRACT_CHARS = 600

SYSTEM_PROMPT = """\
You write short, factual summaries of academic researchers for a directory \
that helps students find research opportunities. You are given only a \
professor's name, institution, research topics, and a handful of their own \
publication titles and abstracts -- nothing else.

The reader already sees this professor's topic tags as separate labels \
displayed right next to your summary. Do not write a summary that just \
restates that list ("Their research topics include X, Y, and Z.") -- that \
tells the reader nothing they can't already see. Topics are context for \
interpreting the publications, not content to report back verbatim. If you \
do use a topic's name, don't just name it: say in plain language what work \
in that area actually involves.

Ground the substance of the summary in what the publications themselves \
describe -- the specific problems, methods, systems, or questions this \
person's own papers are about. A summary built mainly from publication \
content, that never turns into a list of topic names, is the goal.

Write one paragraph (3-5 sentences) describing who they are and what they \
actually work on, grounded strictly in the information given.

Rules:
- Never state anything not directly supported by the provided data. If the \
data is thin (e.g. no publication abstracts), it's fine to fall back on the \
topics to say broadly what area they work in -- but still explain what \
that area means rather than just naming it, and keep the paragraph shorter \
rather than inventing detail.
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
    """OPENAI_API_KEY isn't set -- distinct from a failed generation so
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
    if not os.environ.get("OPENAI_API_KEY"):
        raise SummaryGenerationNotConfigured()

    client = openai.OpenAI()
    prompt = build_summary_prompt(name, institution_name, topics, publications)
    response = client.responses.create(
        model=MODEL,
        instructions=SYSTEM_PROMPT,
        input=prompt,
        max_output_tokens=500,
        reasoning={"effort": "none"},
    )

    # response.status is "incomplete" if generation was cut off (e.g. hit
    # max_output_tokens) rather than finishing normally -- treat that the
    # same as a refusal rather than returning a truncated summary.
    if response.status == "incomplete" or not response.output_text:
        raise SummaryGenerationRefused()
    return response.output_text.strip()
