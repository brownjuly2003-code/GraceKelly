from __future__ import annotations

import unittest

from gracekelly.core.models import models_equivalent, resolve_model


class ModelRegistryTests(unittest.TestCase):
    def test_kimi_alias_maps_to_same_model(self) -> None:
        self.assertTrue(models_equivalent("Kimi K2.5", "Kimi K2"))

    def test_mistral_alias_maps_to_api_model(self) -> None:
        self.assertEqual(resolve_model("Mistral").id, "mistral-small")

    def test_unknown_model_raises(self) -> None:
        with self.assertRaises(ValueError):
            resolve_model("Unknown Model")


if __name__ == "__main__":
    unittest.main()
