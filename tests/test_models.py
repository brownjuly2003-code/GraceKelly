from __future__ import annotations

import unittest

from gracekelly.core.models import (
    ModelSpec,
    list_models,
    models_equivalent,
    normalize_model_name,
    resolve_model,
)


class NormalizeModelNameTests(unittest.TestCase):
    def test_lowercases(self) -> None:
        self.assertEqual(normalize_model_name("GPT-4o"), "gpt 4o")

    def test_strips_whitespace(self) -> None:
        self.assertEqual(normalize_model_name("  Sonar  "), "sonar")

    def test_replaces_dot_with_space(self) -> None:
        self.assertEqual(normalize_model_name("GPT-5.4"), "gpt 5 4")

    def test_replaces_dash_with_space(self) -> None:
        self.assertEqual(normalize_model_name("claude-sonnet"), "claude sonnet")

    def test_replaces_underscore_with_space(self) -> None:
        self.assertEqual(normalize_model_name("my_model_id"), "my model id")

    def test_removes_thinking_suffix(self) -> None:
        self.assertEqual(normalize_model_name("Kimi K2 Thinking"), "kimi k2")

    def test_removes_with_reasoning_suffix(self) -> None:
        self.assertEqual(normalize_model_name("Claude with reasoning"), "claude")

    def test_collapses_multiple_spaces(self) -> None:
        self.assertEqual(normalize_model_name("gpt  5  4"), "gpt 5 4")

    def test_empty_string(self) -> None:
        self.assertEqual(normalize_model_name(""), "")

    def test_already_normalized(self) -> None:
        self.assertEqual(normalize_model_name("sonar"), "sonar")


class ResolveModelTests(unittest.TestCase):
    def test_resolve_by_id(self) -> None:
        spec = resolve_model("sonar")
        self.assertEqual(spec.id, "sonar")

    def test_resolve_by_display_name(self) -> None:
        spec = resolve_model("Sonar")
        self.assertEqual(spec.id, "sonar")

    def test_resolve_by_alias(self) -> None:
        spec = resolve_model("Kimi K2 Thinking")
        self.assertEqual(spec.id, "kimi-k2-5")

    def test_resolve_case_insensitive(self) -> None:
        spec = resolve_model("SONAR")
        self.assertEqual(spec.id, "sonar")

    def test_resolve_api_model(self) -> None:
        spec = resolve_model("mistral-small")
        self.assertEqual(spec.adapter_kind, "api")

    def test_resolve_unknown_raises(self) -> None:
        with self.assertRaises(ValueError):
            resolve_model("not-a-real-model")

    def test_resolve_best(self) -> None:
        spec = resolve_model("Best")
        self.assertEqual(spec.id, "best")

    def test_resolve_with_dot_in_name(self) -> None:
        spec = resolve_model("GPT-5.4")
        self.assertEqual(spec.id, "gpt-5-4")


class ModelsEquivalentTests(unittest.TestCase):
    def test_same_model_id(self) -> None:
        self.assertTrue(models_equivalent("sonar", "sonar"))

    def test_id_and_display_name(self) -> None:
        self.assertTrue(models_equivalent("sonar", "Sonar"))

    def test_alias_and_id(self) -> None:
        self.assertTrue(models_equivalent("Kimi K2 Thinking", "kimi-k2-5"))

    def test_different_models(self) -> None:
        self.assertFalse(models_equivalent("sonar", "best"))

    def test_unknown_left_returns_false(self) -> None:
        self.assertFalse(models_equivalent("ghost-model", "sonar"))

    def test_unknown_right_returns_false(self) -> None:
        self.assertFalse(models_equivalent("sonar", "ghost-model"))

    def test_both_unknown_returns_false(self) -> None:
        self.assertFalse(models_equivalent("x", "y"))


class ListModelsTests(unittest.TestCase):
    def test_returns_tuple(self) -> None:
        self.assertIsInstance(list_models(), tuple)

    def test_non_empty(self) -> None:
        self.assertGreater(len(list_models()), 0)

    def test_all_model_specs(self) -> None:
        for spec in list_models():
            self.assertIsInstance(spec, ModelSpec)

    def test_contains_sonar(self) -> None:
        ids = [spec.id for spec in list_models()]
        self.assertIn("sonar", ids)

    def test_contains_api_model(self) -> None:
        adapter_kinds = {spec.adapter_kind for spec in list_models()}
        self.assertIn("api", adapter_kinds)


class ModelSpecNormalizedNamesTests(unittest.TestCase):
    def test_includes_id(self) -> None:
        spec = resolve_model("sonar")
        normalized_id = normalize_model_name(spec.id)
        self.assertIn(normalized_id, spec.normalized_names())

    def test_includes_display_name(self) -> None:
        spec = resolve_model("sonar")
        normalized_display = normalize_model_name(spec.display_name)
        self.assertIn(normalized_display, spec.normalized_names())

    def test_includes_aliases(self) -> None:
        spec = resolve_model("kimi-k2-5")
        # "Kimi K2 Thinking" alias should be normalized to "kimi k2"
        self.assertIn("kimi k2", spec.normalized_names())

    def test_returns_set(self) -> None:
        spec = resolve_model("sonar")
        self.assertIsInstance(spec.normalized_names(), set)

    def test_reasoning_capable_flag(self) -> None:
        best = resolve_model("best")
        sonar = resolve_model("sonar")
        self.assertTrue(best.reasoning_capable)
        self.assertFalse(sonar.reasoning_capable)


if __name__ == "__main__":
    unittest.main()
