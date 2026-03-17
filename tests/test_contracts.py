from __future__ import annotations

import unittest

from gracekelly.core.contracts import FailureCode
from gracekelly.schemas import TaskStepView
from gracekelly.storage.base import TaskStepRecord
from gracekelly.storage.memory import InMemoryTaskRepository


class FailureCodeTests(unittest.TestCase):
    def test_failure_taxonomy_is_stable(self) -> None:
        self.assertEqual(FailureCode.AUTH_FAILED.value, "auth_failed")
        self.assertEqual(FailureCode.MODEL_MISMATCH.value, "model_mismatch")
        self.assertEqual(FailureCode.PROVIDER_UNAVAILABLE.value, "provider_unavailable")
        self.assertEqual(FailureCode.TIMEOUT.value, "timeout")
        self.assertEqual(FailureCode.RATE_LIMITED.value, "rate_limited")
        self.assertEqual(FailureCode.STORAGE_FAILED.value, "storage_failed")
        self.assertEqual(FailureCode.UNKNOWN_ERROR.value, "unknown_error")

    def test_task_step_view_truncates_long_output(self) -> None:
        record = TaskStepRecord(
            task_id="task-1",
            step_index=1,
            model_id="kimi-k2-5",
            model_display_name="Kimi K2.5",
            backend="browser",
            provider="perplexity",
            status="completed",
            output_text="x" * 12,
        )

        view = TaskStepView.from_record(record, max_output_length=5)

        self.assertEqual(view.output_text, "xxxxx")
        self.assertTrue(view.output_truncated)

    def test_memory_repository_schema_report_is_non_applicable_but_ok(self) -> None:
        repository = InMemoryTaskRepository()

        report = repository.schema_report()

        self.assertEqual(report["status"], "ok")
        self.assertEqual(report["backend"], "memory")
        self.assertEqual(report["schema_version"], "not_applicable")


if __name__ == "__main__":
    unittest.main()
