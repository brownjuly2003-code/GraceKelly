from __future__ import annotations

import unittest
from datetime import UTC, datetime, timedelta

from gracekelly.api.routes.models import (
    _browser_menu_observation,
    _is_newer,
    _last_verified_at,
    _model_catalog_item,
)
from gracekelly.core.models import MODEL_SPECS

_NOW = datetime(2026, 1, 1, 12, 0, tzinfo=UTC)
_EARLIER = _NOW - timedelta(hours=1)
_LATER = _NOW + timedelta(hours=1)


class IsNewerTests(unittest.TestCase):
    """All 5 edge cases of _is_newer(left, right)."""

    def test_both_none_returns_false(self) -> None:
        self.assertFalse(_is_newer(None, None))

    def test_left_none_right_datetime_returns_false(self) -> None:
        self.assertFalse(_is_newer(None, _NOW))

    def test_left_datetime_right_none_returns_true(self) -> None:
        """left is set and right is absent → left is newer."""
        self.assertTrue(_is_newer(_NOW, None))

    def test_left_newer_than_right_returns_true(self) -> None:
        self.assertTrue(_is_newer(_LATER, _NOW))

    def test_left_older_than_right_returns_false(self) -> None:
        self.assertFalse(_is_newer(_EARLIER, _NOW))

    def test_equal_datetimes_returns_false(self) -> None:
        """Equal timestamps: left is not strictly newer."""
        self.assertFalse(_is_newer(_NOW, _NOW))


class BrowserMenuObservationEdgeCasesTests(unittest.TestCase):
    """Edge cases not covered by the main test_models_route.py."""

    def test_healthcheck_returns_non_dict(self) -> None:
        class FakeAdapter:
            def healthcheck(self) -> str:  # type: ignore[override]
                return "not a dict"

        labels, checked, source, verified, picker = _browser_menu_observation(FakeAdapter())
        self.assertEqual(labels, [])
        self.assertIsNone(checked)
        self.assertIsNone(source)
        self.assertEqual(verified, {})
        self.assertIsNone(picker)

    def test_automation_not_a_dict(self) -> None:
        class FakeAdapter:
            def healthcheck(self) -> dict:
                return {"automation": "string, not dict"}

        labels, _, _, _, _ = _browser_menu_observation(FakeAdapter())
        self.assertEqual(labels, [])

    def test_observed_model_menu_not_a_list(self) -> None:
        class FakeAdapter:
            def healthcheck(self) -> dict:
                return {"automation": {"observed_model_menu": "GPT-5.4"}}

        labels, _, _, _, _ = _browser_menu_observation(FakeAdapter())
        self.assertEqual(labels, [])

    def test_verified_labels_non_str_keys_filtered_out(self) -> None:
        """Keys that are not strings must be silently dropped."""
        class FakeAdapter:
            def healthcheck(self) -> dict:
                return {
                    "automation": {
                        "observed_model_menu": ["GPT-5.4"],
                        "observed_model_menu_at": None,
                        "observed_model_menu_source": None,
                        "verified_model_labels_at": {
                            "GPT-5.4": _NOW,
                            123: _NOW,  # non-str key — must be dropped
                        },
                        "last_model_picker_unavailable_at": None,
                    }
                }

        _, _, _, verified, _ = _browser_menu_observation(FakeAdapter())
        self.assertIn("GPT-5.4", verified)
        self.assertNotIn(123, verified)
        self.assertEqual(len(verified), 1)

    def test_verified_labels_non_datetime_values_filtered_out(self) -> None:
        class FakeAdapter:
            def healthcheck(self) -> dict:
                return {
                    "automation": {
                        "observed_model_menu": ["GPT-5.4"],
                        "observed_model_menu_at": None,
                        "observed_model_menu_source": None,
                        "verified_model_labels_at": {
                            "GPT-5.4": "2026-01-01",  # not a datetime
                        },
                        "last_model_picker_unavailable_at": None,
                    }
                }

        _, _, _, verified, _ = _browser_menu_observation(FakeAdapter())
        self.assertEqual(verified, {})

    def test_picker_unavailable_at_non_datetime_becomes_none(self) -> None:
        class FakeAdapter:
            def healthcheck(self) -> dict:
                return {
                    "automation": {
                        "observed_model_menu": [],
                        "observed_model_menu_at": None,
                        "observed_model_menu_source": None,
                        "verified_model_labels_at": {},
                        "last_model_picker_unavailable_at": "2026-01-01",  # not datetime
                    }
                }

        _, _, _, _, picker = _browser_menu_observation(FakeAdapter())
        self.assertIsNone(picker)

    def test_picker_unavailable_at_datetime_preserved(self) -> None:
        class FakeAdapter:
            def healthcheck(self) -> dict:
                return {
                    "automation": {
                        "observed_model_menu": [],
                        "observed_model_menu_at": None,
                        "observed_model_menu_source": None,
                        "verified_model_labels_at": {},
                        "last_model_picker_unavailable_at": _NOW,
                    }
                }

        _, _, _, _, picker = _browser_menu_observation(FakeAdapter())
        self.assertEqual(picker, _NOW)


class LastVerifiedAtAliasTests(unittest.TestCase):
    """_last_verified_at also resolves via models_equivalent alias matching."""

    def test_alias_match_returns_verified_at(self) -> None:
        # "Kimi K2.5" and "Kimi K2" are equivalent via models_equivalent
        result = _last_verified_at("Kimi K2.5", {"Kimi K2": _NOW})
        self.assertEqual(result, _NOW)

    def test_no_alias_match_returns_none(self) -> None:
        result = _last_verified_at("sonar", {"GPT-5.4": _NOW})
        self.assertIsNone(result)


class ModelCatalogItemPickerNewerTests(unittest.TestCase):
    """Tests for _model_catalog_item branches involving picker_newer logic."""

    def _browser_spec(self):  # type: ignore[no-untyped-def]
        return next(s for s in MODEL_SPECS if s.adapter_kind == "browser")

    def test_picker_newer_than_observation_updates_checked_at(self) -> None:
        """When picker became unavailable AFTER last observation, checked_at is replaced."""
        spec = self._browser_spec()
        item = _model_catalog_item(
            spec,
            observed_browser_labels=[spec.provider_model_id],
            observed_browser_checked_at=_EARLIER,
            observed_browser_source="menu",
            verified_browser_labels_at={},
            last_model_picker_unavailable_at=_NOW,  # newer than _EARLIER
        )
        # availability_checked_at should be set to picker time, not observation time
        self.assertEqual(item.availability_checked_at, _NOW)

    def test_picker_newer_than_verification_gives_unverified_status(self) -> None:
        """Even if last_verified_at exists, if picker was unavailable AFTER it,
        status should be 'observed_unverified'."""
        spec = self._browser_spec()
        item = _model_catalog_item(
            spec,
            observed_browser_labels=[spec.provider_model_id],
            observed_browser_checked_at=_EARLIER,
            observed_browser_source="menu",
            verified_browser_labels_at={spec.provider_model_id: _EARLIER},
            last_model_picker_unavailable_at=_NOW,  # newer than verification
        )
        self.assertEqual(item.availability_status, "observed_unverified")

    def test_picker_older_than_verification_gives_available_status(self) -> None:
        """If picker unavailability is older than last_verified_at, model is verified."""
        spec = self._browser_spec()
        item = _model_catalog_item(
            spec,
            observed_browser_labels=[spec.provider_model_id],
            observed_browser_checked_at=_EARLIER,
            observed_browser_source="menu",
            verified_browser_labels_at={spec.provider_model_id: _NOW},
            last_model_picker_unavailable_at=_EARLIER,  # older than verification
        )
        self.assertEqual(item.availability_status, "observed_available")

    def test_unknown_status_uses_picker_unavailable_at_as_checked_at(self) -> None:
        """When no labels observed but picker_unavailable_at is set,
        availability_checked_at should be the picker timestamp."""
        spec = self._browser_spec()
        item = _model_catalog_item(
            spec,
            observed_browser_labels=[],  # no labels → "unknown"
            observed_browser_checked_at=None,
            observed_browser_source=None,
            verified_browser_labels_at={},
            last_model_picker_unavailable_at=_NOW,
        )
        self.assertEqual(item.availability_status, "unknown")
        self.assertEqual(item.availability_checked_at, _NOW)

    def test_unknown_status_fallback_to_observed_checked_at(self) -> None:
        """When no labels and no picker time, checked_at uses observed_browser_checked_at."""
        spec = self._browser_spec()
        item = _model_catalog_item(
            spec,
            observed_browser_labels=[],
            observed_browser_checked_at=_EARLIER,
            observed_browser_source=None,
            verified_browser_labels_at={},
            last_model_picker_unavailable_at=None,
        )
        self.assertEqual(item.availability_status, "unknown")
        self.assertEqual(item.availability_checked_at, _EARLIER)


if __name__ == "__main__":
    unittest.main()
