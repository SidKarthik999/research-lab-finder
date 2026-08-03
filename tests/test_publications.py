from src.ingestion.publications import reconstruct_abstract, strip_markup


class TestStripMarkup:
    def test_strips_mathml_tags(self):
        assert strip_markup("A study of <mml:math>x^2</mml:math> decay") == (
            "A study of x^2 decay"
        )

    def test_collapses_whitespace_left_by_stripped_tags(self):
        assert strip_markup("Before<tag>  </tag>After") == "Before After"

    def test_none_input_returns_none(self):
        assert strip_markup(None) is None

    def test_empty_string_returns_empty_string(self):
        assert strip_markup("") == ""

    def test_text_without_markup_is_unchanged(self):
        assert strip_markup("A plain title") == "A plain title"


class TestReconstructAbstract:
    def test_reconstructs_simple_abstract(self):
        index = {"This": [0], "is": [1], "a": [2], "test": [3]}
        assert reconstruct_abstract(index) == "This is a test"

    def test_handles_repeated_word_at_multiple_positions(self):
        index = {"the": [0, 3], "cat": [1], "and": [2], "dog": [4]}
        assert reconstruct_abstract(index) == "the cat and the dog"

    def test_fills_gap_positions_with_empty_string(self):
        # position 1 is never referenced by any word
        index = {"first": [0], "third": [2]}
        assert reconstruct_abstract(index) == "first  third"
