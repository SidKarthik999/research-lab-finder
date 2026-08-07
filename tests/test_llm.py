import datetime

from backend.llm import build_summary_prompt


class TestBuildSummaryPrompt:
    def test_includes_name_and_institution(self):
        prompt = build_summary_prompt("Ada Lovelace", "Test University", [], [])
        assert "Professor: Ada Lovelace" in prompt
        assert "Institution: Test University" in prompt

    def test_missing_institution_does_not_render_as_none(self):
        prompt = build_summary_prompt("Ada Lovelace", None, [], [])
        assert "None" not in prompt
        assert "Institution: (unknown)" in prompt

    def test_no_topics_says_so_rather_than_being_blank(self):
        prompt = build_summary_prompt("Ada Lovelace", "Test University", [], [])
        assert "(no listed research topics)" in prompt

    def test_topics_are_listed_by_name(self):
        topics = [{"name": "Computational Biology"}, {"name": "Genomics"}]
        prompt = build_summary_prompt("Ada Lovelace", "Test University", topics, [])
        assert "- Computational Biology" in prompt
        assert "- Genomics" in prompt

    def test_no_publications_says_so_rather_than_being_blank(self):
        prompt = build_summary_prompt("Ada Lovelace", "Test University", [], [])
        assert "(no publications on file)" in prompt

    def test_publication_with_abstract_and_year(self):
        publications = [
            {
                "title": "On Computable Numbers",
                "abstract": "A study of computability.",
                "publication_date": datetime.date(1936, 5, 1),
            }
        ]
        prompt = build_summary_prompt("Ada Lovelace", "Test University", [], publications)
        assert "- On Computable Numbers (1936)" in prompt
        assert "Abstract: A study of computability." in prompt

    def test_publication_missing_abstract_omits_abstract_line(self):
        publications = [
            {"title": "Untitled Work", "abstract": None, "publication_date": None}
        ]
        prompt = build_summary_prompt("Ada Lovelace", "Test University", [], publications)
        assert "- Untitled Work" in prompt
        assert "Abstract:" not in prompt

    def test_publication_missing_date_omits_year_parens(self):
        publications = [
            {"title": "Untitled Work", "abstract": None, "publication_date": None}
        ]
        prompt = build_summary_prompt("Ada Lovelace", "Test University", [], publications)
        assert "Untitled Work (" not in prompt

    def test_publication_missing_title_falls_back_rather_than_blank_line(self):
        publications = [
            {"title": None, "abstract": None, "publication_date": None}
        ]
        prompt = build_summary_prompt("Ada Lovelace", "Test University", [], publications)
        assert "(untitled)" in prompt

    def test_long_abstract_is_truncated(self):
        long_abstract = "x" * 1000
        publications = [
            {"title": "Long Paper", "abstract": long_abstract, "publication_date": None}
        ]
        prompt = build_summary_prompt("Ada Lovelace", "Test University", [], publications)
        assert long_abstract not in prompt
        assert "..." in prompt

    def test_short_abstract_is_not_truncated(self):
        short_abstract = "A short abstract."
        publications = [
            {"title": "Short Paper", "abstract": short_abstract, "publication_date": None}
        ]
        prompt = build_summary_prompt("Ada Lovelace", "Test University", [], publications)
        assert f"Abstract: {short_abstract}" in prompt
        assert "..." not in prompt
