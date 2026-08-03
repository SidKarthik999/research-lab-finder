from src.ingestion.enrich_names import is_safe_replacement, normalize_casing


class TestNormalizeCasing:
    def test_title_cases_all_caps_name(self):
        assert normalize_casing("ANNA GOUSSIOU") == "Anna Goussiou"

    def test_title_cases_all_lowercase_name(self):
        assert normalize_casing("anna goussiou") == "Anna Goussiou"

    def test_leaves_already_mixed_case_name_untouched(self):
        assert normalize_casing("Anna Goussiou") == "Anna Goussiou"

    def test_keeps_lowercase_particle_regardless_of_input_case(self):
        assert normalize_casing("JOHN VON NEUMANN") == "John von Neumann"

    def test_title_cases_apostrophe_name_correctly(self):
        assert normalize_casing("O'BRIEN") == "O'Brien"

    def test_leaves_bare_initial_untouched(self):
        # len(core) > 1 guard: a single-letter initial like "A." shouldn't be
        # touched by casing normalization -- it's not a casing problem.
        assert normalize_casing("A. LITKE") == "A. Litke"


class TestIsSafeReplacement:
    def test_accepts_expansion_of_bare_initial(self):
        assert is_safe_replacement("A. M. Litke", "Alan M. Litke") is True

    def test_rejects_replacement_with_more_initials(self):
        assert is_safe_replacement("Alan Litke", "A. Litke") is False

    def test_rejects_mismatched_surname(self):
        assert is_safe_replacement("Alan Litke", "Alan Smith") is False

    def test_rejects_mismatched_first_letter(self):
        assert is_safe_replacement("Alan Litke", "Brian Litke") is False

    def test_rejects_empty_candidate(self):
        assert is_safe_replacement("Alan Litke", "") is False

    def test_rejects_empty_current(self):
        assert is_safe_replacement("", "Alan Litke") is False

    def test_accepts_unchanged_initial_count(self):
        assert is_safe_replacement("A. M. Litke", "A. K. Litke") is True
