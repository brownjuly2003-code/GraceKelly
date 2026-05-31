from __future__ import annotations

import unittest

from gracekelly.core.models import (
    build_browser_model_spec,
    clear_browser_catalog,
    list_models,
    models_equivalent,
    normalize_model_name,
    resolve_model,
)


class NormalizeModelNameTests(unittest.TestCase):
    def test_lowercases_input(self) -> None:
        self.assertEqual(normalize_model_name("MISTRAL"), "mistral")

    def test_strips_whitespace(self) -> None:
        self.assertEqual(normalize_model_name("  Sonar  "), "sonar")

    def test_replaces_dots_with_spaces(self) -> None:
        self.assertEqual(normalize_model_name("GPT-5.4"), "gpt 5 4")

    def test_replaces_hyphens_with_spaces(self) -> None:
        self.assertEqual(normalize_model_name("claude-opus"), "claude opus")

    def test_replaces_underscores_with_spaces(self) -> None:
        self.assertEqual(normalize_model_name("kimi_k2"), "kimi k2")

    def test_strips_thinking_suffix(self) -> None:
        self.assertEqual(normalize_model_name("Kimi K2 Thinking"), "kimi k2")

    def test_strips_with_reasoning_suffix(self) -> None:
        self.assertEqual(normalize_model_name("GPT-5.4 with reasoning"), "gpt 5 4")

    def test_collapses_multiple_spaces(self) -> None:
        self.assertEqual(normalize_model_name("kimi   k2"), "kimi k2")

    def test_empty_string_returns_empty(self) -> None:
        self.assertEqual(normalize_model_name(""), "")


class ModelSpecNormalizedNamesTests(unittest.TestCase):
    def test_normalized_names_includes_id(self) -> None:
        spec = resolve_model("GPT-5.4 API")
        self.assertIn("gpt 5 4 api", spec.normalized_names())

    def test_normalized_names_includes_display_name(self) -> None:
        spec = resolve_model("GPT-5.4 API")
        self.assertIn("gpt 5 4 api", spec.normalized_names())

    def test_normalized_names_includes_aliases(self) -> None:
        spec = resolve_model("Kimi K2.5")
        names = spec.normalized_names()
        self.assertIn("kimi k2 5", names)
        self.assertIn("kimi k2", names)
        self.assertIn("kimi", names)

    def test_thinking_alias_normalizes_correctly(self) -> None:
        spec = resolve_model("Kimi K2.5")
        names = spec.normalized_names()
        # "Kimi K2 Thinking" → "kimi k2" after stripping " thinking"
        self.assertIn("kimi k2", names)


class ListModelsTests(unittest.TestCase):
    def test_returns_tuple(self) -> None:
        self.assertIsInstance(list_models(), tuple)

    def test_returns_non_empty_registry(self) -> None:
        self.assertGreater(len(list_models()), 0)

    def test_all_entries_have_unique_ids(self) -> None:
        ids = [m.id for m in list_models()]
        self.assertEqual(len(ids), len(set(ids)))

    def test_all_entries_have_timeout_seconds(self) -> None:
        for spec in list_models():
            self.assertGreater(spec.timeout_seconds, 0)

    def test_registry_contains_api_and_browser_adapters(self) -> None:
        kinds = {m.adapter_kind for m in list_models()}
        self.assertIn("api", kinds)
        self.assertIn("browser", kinds)


class ModelRegistryTests(unittest.TestCase):
    def test_kimi_alias_maps_to_same_model(self) -> None:
        self.assertTrue(models_equivalent("Kimi K2.5", "Kimi K2"))

    def test_removed_mistral_alias_is_unsupported(self) -> None:
        with self.assertRaises(ValueError):
            resolve_model("mistral")

    def test_browser_compatibility_alias_resolves_without_catalog_snapshot(self) -> None:
        clear_browser_catalog()
        spec = resolve_model("claude-sonnet-4-6")
        self.assertEqual(spec.id, "claude-sonnet-4-6")
        self.assertEqual(spec.provider_model_id, "Claude Sonnet 4.6")

    def test_recon_observed_browser_models_resolve_from_registry(self) -> None:
        self.assertEqual(resolve_model("Best").id, "best")
        self.assertEqual(resolve_model("Sonar").id, "sonar")
        self.assertEqual(resolve_model("Claude Opus").id, "claude-opus-4-6")
        self.assertEqual(resolve_model("Max").id, "max")
        self.assertEqual(resolve_model("Nemotron 3").id, "nemotron-3-super")

    def test_thinking_is_not_a_model(self) -> None:
        with self.assertRaises(ValueError):
            resolve_model("Thinking")

    def test_sonar_is_search_not_reasoning(self) -> None:
        spec = resolve_model("Sonar")
        self.assertFalse(spec.reasoning_capable)
        self.assertEqual(spec.expected_latency_class, "fast")

    def test_sonar_2_is_search_not_reasoning(self) -> None:
        spec = build_browser_model_spec("Sonar 2")
        self.assertEqual(spec.id, "sonar-2")
        self.assertFalse(spec.reasoning_capable)
        self.assertEqual(spec.expected_latency_class, "fast")

    def test_unknown_model_raises(self) -> None:
        with self.assertRaises(ValueError):
            resolve_model("Unknown Model")

    def test_resolve_model_case_insensitive(self) -> None:
        with self.assertRaises(ValueError):
            resolve_model("mistral")

    def test_resolve_model_with_dots_in_name(self) -> None:
        self.assertEqual(resolve_model("GPT-5.4").id, "gpt-5-4")

    def test_resolve_model_alias_via_thinking_suffix(self) -> None:
        """'Kimi K2 Thinking' normalizes to 'kimi k2' which matches kimi-k2-5."""
        self.assertEqual(resolve_model("Kimi K2 Thinking").id, "kimi-k2-5")


class ModelsEquivalentTests(unittest.TestCase):
    def test_same_model_different_aliases_is_equivalent(self) -> None:
        self.assertTrue(models_equivalent("Kimi K2.5", "Kimi K2"))

    def test_same_string_is_equivalent(self) -> None:
        self.assertTrue(models_equivalent("GPT-5.4 API", "GPT-5.4 API"))

    def test_different_models_not_equivalent(self) -> None:
        self.assertFalse(models_equivalent("GPT-5.4 API", "Sonar"))

    def test_one_unknown_model_returns_false(self) -> None:
        self.assertFalse(models_equivalent("GPT-5.4 API", "NoSuchModel"))

    def test_both_unknown_models_returns_false(self) -> None:
        self.assertFalse(models_equivalent("NoSuchA", "NoSuchB"))

    def test_api_and_browser_variant_not_equivalent(self) -> None:
        """GPT-5.4 (browser) and GPT-5.4 API (api) are different models."""
        self.assertFalse(models_equivalent("GPT-5.4", "GPT-5.4 API"))


if __name__ == "__main__":
    unittest.main()
