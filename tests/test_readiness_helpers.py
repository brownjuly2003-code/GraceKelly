from __future__ import annotations

import unittest
from typing import Any

from gracekelly.core.readiness import (
    adapter_component_status,
    execution_component_status,
    storage_component_status,
)


class _FakeRepository:
    """Minimal fake that implements TaskRepository's healthcheck/schema_report."""

    def __init__(
        self,
        *,
        backend_name: str = "fake",
        health_status: str = "ok",
        schema_status: str = "ok",
        health_extra: dict[str, Any] | None = None,
    ) -> None:
        self.backend_name = backend_name
        self._health_status = health_status
        self._schema_status = schema_status
        self._health_extra = health_extra or {}

    def healthcheck(self) -> dict[str, Any]:
        return {"status": self._health_status, **self._health_extra}

    def schema_report(self) -> dict[str, Any]:
        return {"status": self._schema_status}


class _FakeHealthcheck:
    def healthcheck(self) -> dict[str, Any]:
        return {"status": "ok", "backend": "fake"}


class _FakeHealthcheckDegraded:
    def healthcheck(self) -> dict[str, Any]:
        return {"status": "degraded"}


class _NoHealthcheck:
    """Object that does NOT implement SupportsHealthcheck."""
    pass


class StorageComponentStatusTests(unittest.TestCase):
    def test_both_ok_returns_ok(self) -> None:
        repo = _FakeRepository(health_status="ok", schema_status="ok")
        result = storage_component_status(repo, required=True)
        self.assertEqual(result["status"], "ok")

    def test_health_failed_returns_failed(self) -> None:
        repo = _FakeRepository(health_status="failed", schema_status="ok")
        result = storage_component_status(repo, required=True)
        self.assertEqual(result["status"], "failed")

    def test_schema_failed_returns_failed(self) -> None:
        repo = _FakeRepository(health_status="ok", schema_status="failed")
        result = storage_component_status(repo, required=True)
        self.assertEqual(result["status"], "failed")

    def test_health_failed_beats_schema_degraded(self) -> None:
        repo = _FakeRepository(health_status="failed", schema_status="degraded")
        result = storage_component_status(repo, required=True)
        self.assertEqual(result["status"], "failed")

    def test_health_degraded_returns_degraded(self) -> None:
        repo = _FakeRepository(health_status="degraded", schema_status="ok")
        result = storage_component_status(repo, required=True)
        self.assertEqual(result["status"], "degraded")

    def test_schema_degraded_returns_degraded(self) -> None:
        repo = _FakeRepository(health_status="ok", schema_status="degraded")
        result = storage_component_status(repo, required=True)
        self.assertEqual(result["status"], "degraded")

    def test_kind_is_storage(self) -> None:
        repo = _FakeRepository()
        result = storage_component_status(repo, required=True)
        self.assertEqual(result["kind"], "storage")

    def test_name_matches_backend_name(self) -> None:
        repo = _FakeRepository(backend_name="postgres")
        result = storage_component_status(repo, required=True)
        self.assertEqual(result["name"], "postgres")

    def test_required_flag_passed_through_true(self) -> None:
        repo = _FakeRepository()
        result = storage_component_status(repo, required=True)
        self.assertTrue(result["required"])

    def test_required_flag_passed_through_false(self) -> None:
        repo = _FakeRepository()
        result = storage_component_status(repo, required=False)
        self.assertFalse(result["required"])

    def test_details_includes_schema_key(self) -> None:
        repo = _FakeRepository()
        result = storage_component_status(repo, required=True)
        self.assertIn("schema", result["details"])

    def test_details_includes_health_keys(self) -> None:
        repo = _FakeRepository(health_extra={"task_count": 5})
        result = storage_component_status(repo, required=True)
        self.assertIn("task_count", result["details"])


class ExecutionComponentStatusTests(unittest.TestCase):
    def test_non_healthcheck_object_returns_unknown(self) -> None:
        result = execution_component_status(_NoHealthcheck())
        self.assertEqual(result["status"], "unknown")

    def test_healthcheck_object_returns_its_status(self) -> None:
        result = execution_component_status(_FakeHealthcheck())
        self.assertEqual(result["status"], "ok")

    def test_degraded_healthcheck_propagated(self) -> None:
        result = execution_component_status(_FakeHealthcheckDegraded())
        self.assertEqual(result["status"], "degraded")

    def test_kind_is_execution(self) -> None:
        result = execution_component_status(_FakeHealthcheck())
        self.assertEqual(result["kind"], "execution")

    def test_name_is_execution_router(self) -> None:
        result = execution_component_status(_FakeHealthcheck())
        self.assertEqual(result["name"], "execution-router")

    def test_required_is_always_true(self) -> None:
        result = execution_component_status(_FakeHealthcheck())
        self.assertTrue(result["required"])

    def test_details_contains_healthcheck_output(self) -> None:
        result = execution_component_status(_FakeHealthcheck())
        self.assertEqual(result["details"].get("backend"), "fake")

    def test_non_healthcheck_details_contain_unknown_status(self) -> None:
        result = execution_component_status(_NoHealthcheck())
        self.assertEqual(result["details"].get("status"), "unknown")

    def test_none_is_not_healthcheck(self) -> None:
        """None should not match SupportsHealthcheck and must not crash."""
        result = execution_component_status(None)
        self.assertEqual(result["status"], "unknown")


class AdapterComponentStatusTests(unittest.TestCase):
    def test_non_healthcheck_returns_unknown(self) -> None:
        result = adapter_component_status("my-adapter", _NoHealthcheck(), required=True)
        self.assertEqual(result["status"], "unknown")

    def test_healthcheck_returns_its_status(self) -> None:
        result = adapter_component_status("my-adapter", _FakeHealthcheck(), required=True)
        self.assertEqual(result["status"], "ok")

    def test_kind_is_adapter(self) -> None:
        result = adapter_component_status("my-adapter", _FakeHealthcheck(), required=True)
        self.assertEqual(result["kind"], "adapter")

    def test_name_is_passed_through(self) -> None:
        result = adapter_component_status("browser-adapter", _FakeHealthcheck(), required=True)
        self.assertEqual(result["name"], "browser-adapter")

    def test_required_true_passed_through(self) -> None:
        result = adapter_component_status("x", _FakeHealthcheck(), required=True)
        self.assertTrue(result["required"])

    def test_required_false_passed_through(self) -> None:
        result = adapter_component_status("x", _FakeHealthcheck(), required=False)
        self.assertFalse(result["required"])

    def test_details_contains_healthcheck_output(self) -> None:
        result = adapter_component_status("x", _FakeHealthcheck(), required=True)
        self.assertIn("backend", result["details"])

    def test_degraded_adapter_propagated(self) -> None:
        result = adapter_component_status("x", _FakeHealthcheckDegraded(), required=True)
        self.assertEqual(result["status"], "degraded")

    def test_none_adapter_returns_unknown(self) -> None:
        result = adapter_component_status("x", None, required=False)
        self.assertEqual(result["status"], "unknown")


if __name__ == "__main__":
    unittest.main()
