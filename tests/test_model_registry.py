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
        self.assertEqual(resolve_model("Thinking").id, "thinking")
        self.assertEqual(resolve_model("Max").id, "max")
        self.assertEqual(resolve_model("Nemotron 3").id, "nemotron-3-super")

    def test_thinking_model_is_reasoning_capable(self) -> None:
        spec = resolve_model("Thinking")
        self.assertTrue(spec.reasoning_capable)
        self.assertEqual(spec.adapter_kind, "browser")
        self.assertEqual(spec.provider, "perplexity")
        self.assertEqual(spec.timeout_seconds, 120)

    def test_unknown_model_raises(self) -> None:
        with self.assertRaises(ValueError):
            resolve_model("Unknown Model")


if __name__ == "__main__":
    unittest.main()
