from __future__ import annotations

import unittest

from gracekelly.core.models import (
    MODEL_SPECS,
    list_models,
    models_equivalent,
    normalize_model_name,
    resolve_model,
)


class NormalizeModelNameEdgeTests(unittest.TestCase):
    """Additional edge cases for normalize_model_name."""

    def test_thinking_substring_mid_word_not_stripped(self) -> None:
        # " thinking" must appear as a separate word to be stripped;
        # "rethinking" should NOT lose its text.
        result = normalize_model_name("rethinking paradigm")
        self.assertIn("rethinking", result)

    def test_with_reasoning_mid_string_not_stripped(self) -> None:
        # " with reasoning" must be exact phrase; extra text is preserved.
        result = normalize_model_name("without reasoning capability")
        self.assertNotEqual(result, "without capability")

    def test_mixed_separators_all_replaced(self) -> None:
        result = normalize_model_name("my-model.v2_test")
        self.assertNotIn("-", result)
        self.assertNotIn(".", result)
        self.assertNotIn("_", result)

    def test_only_spaces_after_normalize(self) -> None:
        result = normalize_model_name("---")
        self.assertEqual(result, "")

    def test_thinking_suffix_stripped_case_insensitive_via_lower(self) -> None:
        # normalize_model_name lowercases first, so " thinking" suffix is stripped
        result = normalize_model_name("Kimi K2 Thinking")
        self.assertNotIn("thinking", result)

    def test_with_reasoning_suffix_stripped(self) -> None:
        result = normalize_model_name("Claude with reasoning")
        self.assertNotIn("reasoning", result)


class ListModelsExactnessTests(unittest.TestCase):
    """list_models returns exactly MODEL_SPECS."""

    def test_list_models_is_model_specs(self) -> None:
        self.assertIs(list_models(), MODEL_SPECS)

    def test_list_models_count_matches_model_specs(self) -> None:
        self.assertEqual(len(list_models()), len(MODEL_SPECS))

    def test_all_specs_have_non_empty_id(self) -> None:
        for spec in list_models():
            self.assertTrue(spec.id, f"Empty id on spec: {spec}")

    def test_all_specs_have_non_empty_provider(self) -> None:
        for spec in list_models():
            self.assertTrue(spec.provider, f"Empty provider on spec: {spec}")

    def test_all_specs_have_positive_timeout(self) -> None:
        for spec in list_models():
            self.assertGreater(spec.timeout_seconds, 0, f"Bad timeout on {spec.id}")

    def test_all_specs_have_positive_concurrency_limit(self) -> None:
        for spec in list_models():
            self.assertGreater(spec.concurrency_limit, 0, f"Bad concurrency on {spec.id}")


class ModelsEquivalentSymmetryTests(unittest.TestCase):
    """models_equivalent should be symmetric."""

    def test_symmetric_same_models(self) -> None:
        self.assertEqual(
            models_equivalent("sonar", "Sonar"),
            models_equivalent("Sonar", "sonar"),
        )

    def test_symmetric_different_models(self) -> None:
        self.assertEqual(
            models_equivalent("sonar", "best"),
            models_equivalent("best", "sonar"),
        )

    def test_symmetric_unknown_model(self) -> None:
        self.assertEqual(
            models_equivalent("ghost", "sonar"),
            models_equivalent("sonar", "ghost"),
        )

    def test_both_unknown_symmetric(self) -> None:
        self.assertEqual(
            models_equivalent("x", "y"),
            models_equivalent("y", "x"),
        )


class ModelSpecNormalizedNamesAdditionalTests(unittest.TestCase):
    """Additional normalized_names() tests for alias de-duplication."""

    def test_aliases_are_normalized(self) -> None:
        spec = resolve_model("kimi-k2-5")
        # All aliases should produce normalized entries in the set
        for alias in spec.aliases:
            normalized_alias = normalize_model_name(alias)
            self.assertIn(normalized_alias, spec.normalized_names())

    def test_normalized_names_excludes_raw_mixed_case(self) -> None:
        spec = resolve_model("sonar")
        # Raw mixed-case values must not appear — only normalized ones
        self.assertNotIn("Sonar", spec.normalized_names())

    def test_reasoning_capable_api_model(self) -> None:
        spec = resolve_model("claude-sonnet-4-6-api")
        self.assertTrue(spec.reasoning_capable)

    def test_non_reasoning_api_model(self) -> None:
        spec = resolve_model("mistral-small")
        self.assertFalse(spec.reasoning_capable)

    def test_model_spec_is_immutable(self) -> None:
        spec = resolve_model("sonar")
        with self.assertRaises((AttributeError, TypeError)):
            spec.id = "changed"  # type: ignore[misc]


if __name__ == "__main__":
    unittest.main()
