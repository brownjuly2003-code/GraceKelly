from __future__ import annotations

from datetime import datetime, timezone
import unittest

from gracekelly.core.contracts import FailureCode, MergeStrategy, StepStatus, TaskStatus
from gracekelly.schemas import OrchestrateResponse, TaskStepView
from gracekelly.storage.base import TaskRecord, TaskStepRecord
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

    def test_orchestrate_response_prefers_completed_adapter_over_cancelled_steps(self) -> None:
        now = datetime.now(timezone.utc)
        task = TaskRecord(
            task_id="task-1",
            status=TaskStatus.COMPLETED,
            accepted_at=now,
            completed_at=now,
            duration_ms=1,
            prompt="prompt",
            reasoning=False,
            execution_mode="mixed",
            dry_run=False,
            model_count=2,
            quorum=1,
            merge_strategy=MergeStrategy.FIRST_SUCCESS,
            adapter_hint="auto",
            cancel_on_quorum=True,
            output_text="winner",
        )
        steps = [
            TaskStepRecord(
                task_id="task-1",
                step_index=1,
                model_id="kimi-k2-5",
                model_display_name="Kimi K2.5",
                backend="browser",
                provider="perplexity",
                status=StepStatus.COMPLETED,
            ),
            TaskStepRecord(
                task_id="task-1",
                step_index=2,
                model_id="mistral-small",
                model_display_name="Mistral Small",
                backend="api",
                provider="mistral",
                status=StepStatus.CANCELLED,
            ),
        ]

        response = OrchestrateResponse.from_task(task, steps, [])

        self.assertEqual(response.adapter_name, "browser.perplexity")


if __name__ == "__main__":
    unittest.main()
