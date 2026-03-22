from __future__ import annotations

import unittest

from gracekelly.core.models import models_equivalent, resolve_model


class ModelRegistryTests(unittest.TestCase):
    def test_kimi_alias_maps_to_same_model(self) -> None:
        self.assertTrue(models_equivalent("Kimi K2.5", "Kimi K2"))

    def test_mistral_alias_maps_to_api_model(self) -> None:
        self.assertEqual(resolve_model("Mistral").id, "mistral-small")

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

    def test_unknown_model_raises(self) -> None:
        with self.assertRaises(ValueError):
            resolve_model("Unknown Model")


if __name__ == "__main__":
    unittest.main()
