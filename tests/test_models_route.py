from __future__ import annotations

import unittest
from datetime import UTC, datetime
from types import SimpleNamespace
from unittest.mock import patch

from fastapi import FastAPI
from fastapi.testclient import TestClient

from gracekelly.api.routes.models import (
    _browser_menu_observation,
    _is_observed_browser_model_available,
    _last_verified_at,
    _model_catalog_item,
    router,
)
from gracekelly.core.models import MODEL_SPECS, ModelSpec


class BrowserMenuObservationTests(unittest.TestCase):
    def test_none_adapter(self) -> None:
        labels, checked, source, verified, picker = _browser_menu_observation(None)
        self.assertEqual(labels, [])
        self.assertIsNone(checked)
        self.assertIsNone(source)
        self.assertEqual(verified, {})
        self.assertIsNone(picker)

    def test_adapter_without_healthcheck(self) -> None:
        labels, _, _, _, _ = _browser_menu_observation(object())
        self.assertEqual(labels, [])

    def test_adapter_with_empty_healthcheck(self) -> None:
        class FakeAdapter:
            def healthcheck(self) -> dict[str, object]:
                return {}

        labels, _, _, _, _ = _browser_menu_observation(FakeAdapter())
        self.assertEqual(labels, [])

    def test_adapter_with_valid_observation(self) -> None:
        now = datetime.now(UTC)

        class FakeAdapter:
            def healthcheck(self) -> dict[str, object]:
                return {
                    "automation": {
                        "observed_model_menu": ["GPT-5.4", "Claude Sonnet 4.6"],
                        "observed_model_menu_at": now,
                        "observed_model_menu_source": "perplexity-model-menu",
                        "verified_model_labels_at": {"GPT-5.4": now},
                        "last_model_picker_unavailable_at": None,
                    }
                }

        labels, checked, source, verified, picker = _browser_menu_observation(FakeAdapter())
        self.assertEqual(labels, ["GPT-5.4", "Claude Sonnet 4.6"])
        self.assertEqual(checked, now)
        self.assertEqual(source, "perplexity-model-menu")
        self.assertEqual(verified, {"GPT-5.4": now})
        self.assertIsNone(picker)

    def test_empty_and_whitespace_labels_filtered(self) -> None:
        class FakeAdapter:
            def healthcheck(self) -> dict[str, object]:
                return {
                    "automation": {
                        "observed_model_menu": ["GPT-5.4", "", "  "],
                        "observed_model_menu_at": None,
                        "observed_model_menu_source": None,
                        "verified_model_labels_at": {},
                        "last_model_picker_unavailable_at": None,
                    }
                }

        labels, _, _, _, _ = _browser_menu_observation(FakeAdapter())
        self.assertEqual(labels, ["GPT-5.4"])


class IsObservedBrowserModelAvailableTests(unittest.TestCase):
    def test_exact_match(self) -> None:
        self.assertTrue(_is_observed_browser_model_available("GPT-5.4", ["GPT-5.4", "Best"]))

    def test_alias_match(self) -> None:
        self.assertTrue(_is_observed_browser_model_available("Kimi K2.5", ["Kimi K2"]))

    def test_no_match(self) -> None:
        self.assertFalse(_is_observed_browser_model_available("Kimi K2.5", ["GPT-5.4", "Best"]))

    def test_empty_labels(self) -> None:
        self.assertFalse(_is_observed_browser_model_available("GPT-5.4", []))


class LastVerifiedAtTests(unittest.TestCase):
    def test_exact_match(self) -> None:
        now = datetime.now(UTC)
        result = _last_verified_at("GPT-5.4", {"GPT-5.4": now})
        self.assertEqual(result, now)

    def test_no_match(self) -> None:
        now = datetime.now(UTC)
        result = _last_verified_at("Kimi K2.5", {"GPT-5.4": now})
        self.assertIsNone(result)

    def test_empty_dict(self) -> None:
        self.assertIsNone(_last_verified_at("GPT-5.4", {}))


class ModelCatalogItemTests(unittest.TestCase):
    def _api_spec(self) -> ModelSpec:
        return next(s for s in MODEL_SPECS if s.adapter_kind == "api")

    def _browser_spec(self) -> ModelSpec:
        return next(s for s in MODEL_SPECS if s.adapter_kind == "browser")

    def test_api_model_is_static(self) -> None:
        item = _model_catalog_item(
            self._api_spec(),
            observed_browser_labels=[],
            observed_browser_checked_at=None,
            observed_browser_source=None,
            verified_browser_labels_at={},
            last_model_picker_unavailable_at=None,
        )
        self.assertEqual(item.availability_status, "static")
        self.assertIsNone(item.available)

    def test_browser_model_unknown_without_observation(self) -> None:
        item = _model_catalog_item(
            self._browser_spec(),
            observed_browser_labels=[],
            observed_browser_checked_at=None,
            observed_browser_source=None,
            verified_browser_labels_at={},
            last_model_picker_unavailable_at=None,
        )
        self.assertEqual(item.availability_status, "unknown")
        self.assertIsNone(item.available)

    def test_browser_model_observed_unavailable(self) -> None:
        now = datetime.now(UTC)
        spec = self._browser_spec()
        item = _model_catalog_item(
            spec,
            observed_browser_labels=["SomeOtherModel"],
            observed_browser_checked_at=now,
            observed_browser_source="perplexity-model-menu",
            verified_browser_labels_at={},
            last_model_picker_unavailable_at=None,
        )
        self.assertEqual(item.availability_status, "observed_unavailable")
        self.assertFalse(item.available)

    def test_browser_model_observed_unverified(self) -> None:
        now = datetime.now(UTC)
        spec = self._browser_spec()
        item = _model_catalog_item(
            spec,
            observed_browser_labels=[spec.provider_model_id],
            observed_browser_checked_at=now,
            observed_browser_source="perplexity-model-menu",
            verified_browser_labels_at={},
            last_model_picker_unavailable_at=None,
        )
        self.assertEqual(item.availability_status, "observed_unverified")
        self.assertTrue(item.available)
        self.assertIsNone(item.last_verified_at)

    def test_browser_model_observed_available_verified(self) -> None:
        now = datetime.now(UTC)
        spec = self._browser_spec()
        item = _model_catalog_item(
            spec,
            observed_browser_labels=[spec.provider_model_id],
            observed_browser_checked_at=now,
            observed_browser_source="perplexity-model-menu",
            verified_browser_labels_at={spec.provider_model_id: now},
            last_model_picker_unavailable_at=None,
        )
        self.assertEqual(item.availability_status, "observed_available")
        self.assertTrue(item.available)
        self.assertEqual(item.last_verified_at, now)

    def test_catalog_item_has_all_spec_fields(self) -> None:
        spec = self._api_spec()
        item = _model_catalog_item(
            spec,
            observed_browser_labels=[],
            observed_browser_checked_at=None,
            observed_browser_source=None,
            verified_browser_labels_at={},
            last_model_picker_unavailable_at=None,
        )
        self.assertEqual(item.id, spec.id)
        self.assertEqual(item.display_name, spec.display_name)
        self.assertEqual(item.aliases, list(spec.aliases))
        self.assertEqual(item.adapter_kind, spec.adapter_kind)
        self.assertEqual(item.provider, spec.provider)
        self.assertEqual(item.reasoning_capable, spec.reasoning_capable)
        self.assertEqual(item.timeout_seconds, spec.timeout_seconds)
        self.assertEqual(item.concurrency_limit, spec.concurrency_limit)

    def test_all_specs_produce_valid_catalog_items(self) -> None:
        for spec in MODEL_SPECS:
            item = _model_catalog_item(
                spec,
                observed_browser_labels=[],
                observed_browser_checked_at=None,
                observed_browser_source=None,
                verified_browser_labels_at={},
                last_model_picker_unavailable_at=None,
            )
            self.assertIsNotNone(item.id)
            self.assertIn(item.availability_status, ("static", "unknown"))


class RefreshModelsRouteTests(unittest.TestCase):
    def setUp(self) -> None:
        app = FastAPI()
        app.include_router(router)
        self.client = TestClient(app)

    def test_refresh_models_returns_200(self) -> None:
        with patch(
            "gracekelly.api.routes.models.get_app_state",
            return_value=SimpleNamespace(browser_adapter=None),
        ):
            resp = self.client.post("/api/v1/models/refresh")
        self.assertEqual(resp.status_code, 200)

    def test_refresh_models_has_refreshed_at_and_models(self) -> None:
        with patch(
            "gracekelly.api.routes.models.get_app_state",
            return_value=SimpleNamespace(browser_adapter=None),
        ):
            resp = self.client.post("/api/v1/models/refresh")
        data = resp.json()
        self.assertIn("refreshed_at", data)
        self.assertIn("models", data)
        self.assertIsInstance(data["models"], list)
        self.assertGreater(len(data["models"]), 0)
