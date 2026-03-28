from __future__ import annotations

import unittest
from datetime import UTC, datetime

from gracekelly.adapters.dry_run import DryRunExecutionAdapter
from gracekelly.core.contracts import (
    EventType,
    ExecutionBatchResult,
    ExecutionMode,
    ExecutionResult,
    StepStatus,
    TaskStatus,
)
from gracekelly.core.orchestrator import OrchestratorService, StorageUnavailableError, _EventSequence
from gracekelly.core.planning import build_execution_plan
from gracekelly.core.router import ExecutionRouter
from gracekelly.schemas import OrchestrateRequest
from gracekelly.storage.base import TaskRecord
from gracekelly.storage.memory import InMemoryTaskRepository


class OrchestratorServiceTests(unittest.TestCase):
    def setUp(self) -> None:
        self.repository = InMemoryTaskRepository()
        self.service = OrchestratorService(
            self.repository,
            execution_router=ExecutionRouter(dry_run_adapter=DryRunExecutionAdapter()),
        )

    def test_submit_uses_dry_run_adapter_and_canonical_model(self) -> None:
        request = OrchestrateRequest(
            prompt="health check",
            model="Kimi K2",
            reasoning=True,
            metadata={"trace_id": "abc-123"},
            dry_run=True,
        )

        task = self.service.submit(request)
        steps = self.service.list_task_steps(task.task_id)

        self.assertEqual(task.status, "completed")
        self.assertEqual(task.execution_mode, "dry-run")
        self.assertTrue(task.dry_run)
        self.assertEqual(task.model_count, 1)
        self.assertEqual(task.metadata["trace_id"], "abc-123")
        self.assertEqual(steps, [])
        events = self.service.list_task_events(task.task_id)
        self.assertEqual([item.event_type for item in events], ["task.accepted"])

    def test_submit_snapshot_returns_persisted_steps_without_readback(self) -> None:
        class FakeMistralAdapter:
            name = "api.mistral"

            def execute(self, request):
                from gracekelly.core.contracts import ExecutionResult

                return ExecutionResult(
                    adapter_name=self.name,
                    model_id=request.step.model.id,
                    model_display_name=request.step.model.display_name,
                    execution_mode="api",
                    status=StepStatus.COMPLETED,
                    output_text="api result",
                )

        service = OrchestratorService(
            self.repository,
            execution_router=ExecutionRouter(
                dry_run_adapter=DryRunExecutionAdapter(),
                api_adapters={"mistral": FakeMistralAdapter()},
            ),
        )
        snapshot = service.submit_snapshot(
            OrchestrateRequest(
                prompt="snapshot",
                model="Mistral",
                dry_run=False,
            )
        )

        self.assertEqual(snapshot.task.status, "completed")
        self.assertEqual(len(snapshot.steps), 1)
        self.assertEqual(snapshot.steps[0].status, "completed")

    def test_non_dry_run_api_request_can_complete(self) -> None:
        class FakeMistralAdapter:
            name = "api.mistral"

            def execute(self, request):
                from gracekelly.core.contracts import ExecutionResult

                return ExecutionResult(
                    adapter_name=self.name,
                    model_id=request.step.model.id,
                    model_display_name=request.step.model.display_name,
                    execution_mode="api",
                    status=StepStatus.COMPLETED,
                    output_text="api result",
                    details={"provider": "mistral"},
                )

        self.service = OrchestratorService(
            self.repository,
            execution_router=ExecutionRouter(
                dry_run_adapter=DryRunExecutionAdapter(),
                api_adapters={"mistral": FakeMistralAdapter()},
            ),
        )

        request = OrchestrateRequest(
            prompt="real execution later",
            model="Mistral",
            dry_run=False,
        )

        task = self.service.submit(request)
        steps = self.service.list_task_steps(task.task_id)

        self.assertEqual(task.status, "completed")
        self.assertEqual(task.execution_mode, "api")
        self.assertFalse(task.dry_run)
        self.assertEqual(task.output_text, "api result")
        self.assertEqual(len(steps), 1)
        self.assertEqual(steps[0].model_id, "mistral-small")
        self.assertEqual(steps[0].status, "completed")
        events = self.service.list_task_events(task.task_id)
        self.assertEqual(
            [item.event_type for item in events],
            ["task.accepted", "step.completed", "task.completed"],
        )
        self.assertEqual(events[1].payload["details"]["provider"], "mistral")
        self.assertEqual(events[-1].payload["details"]["adapter_names"], ["api.mistral"])
        self.assertEqual(events[-1].payload["details"]["completed_step_count"], 1)
        self.assertEqual(events[-1].payload["details"]["failed_step_count"], 0)

    def test_failed_task_event_carries_batch_execution_details(self) -> None:
        task = self.service.submit(
            OrchestrateRequest(
                prompt="missing adapter",
                model="Mistral",
                dry_run=False,
            )
        )
        events = self.service.list_task_events(task.task_id)

        self.assertEqual(task.status, "failed")
        self.assertEqual(
            [item.event_type for item in events],
            ["task.accepted", "step.failed", "task.failed"],
        )
        self.assertEqual(events[-1].payload["failure_code"], "provider_unavailable")
        self.assertEqual(events[-1].payload["details"]["adapter_names"], ["api.mistral"])
        self.assertEqual(events[-1].payload["details"]["failed_step_count"], 1)
        self.assertEqual(events[-1].payload["details"]["failure_codes"], ["provider_unavailable"])

    def test_submit_raises_storage_unavailable_when_persistence_fails(self) -> None:
        class FailingRepository(InMemoryTaskRepository):
            def save_task_with_steps(self, task, steps) -> None:
                raise RuntimeError("database is offline")

        service = OrchestratorService(
            FailingRepository(),
            execution_router=ExecutionRouter(dry_run_adapter=DryRunExecutionAdapter()),
        )
        request = OrchestrateRequest(
            prompt="dry run with storage failure",
            model="Kimi K2",
            dry_run=True,
        )

        with self.assertRaises(StorageUnavailableError) as ctx:
            service.submit(request)

        self.assertIn("save_task_with_steps", str(ctx.exception))

    def test_submit_logs_warning_when_event_persistence_fails(self) -> None:
        class EventFailingRepository(InMemoryTaskRepository):
            def append_event(self, event) -> None:
                raise RuntimeError("event sink offline")

        service = OrchestratorService(
            EventFailingRepository(),
            execution_router=ExecutionRouter(dry_run_adapter=DryRunExecutionAdapter()),
        )

        with self.assertLogs("gracekelly.core.orchestrator", level="WARNING") as captured:
            task = service.submit(
                OrchestrateRequest(
                    prompt="event failure logging",
                    model="Kimi K2",
                    dry_run=True,
                )
            )

        self.assertEqual(task.status, "completed")
        self.assertEqual(len(captured.output), 1)
        self.assertIn("task.event_persistence_failed", captured.output[0])
        self.assertIn('event_type="task.accepted"', captured.output[0])
        self.assertIn('message="event sink offline"', captured.output[0])

    def test_submit_logs_trace_aware_task_lifecycle(self) -> None:
        with self.assertLogs("gracekelly.core.orchestrator", level="INFO") as captured:
            task = self.service.submit(
                OrchestrateRequest(
                    prompt="trace aware logging",
                    model="Kimi K2",
                    dry_run=True,
                    metadata={"trace_id": "trace-123"},
                )
            )

        self.assertEqual(task.status, "completed")
        self.assertEqual(len(captured.output), 2)
        self.assertIn("task.submit.started", captured.output[0])
        self.assertIn('trace_id="trace-123"', captured.output[0])
        self.assertIn("task.submit.completed", captured.output[1])
        self.assertIn(f'task_id="{task.task_id}"', captured.output[1])
        self.assertIn('trace_id="trace-123"', captured.output[1])

    def test_submit_records_quorum_short_circuit_in_steps_and_events(self) -> None:
        class FakeBrowserAdapter:
            name = "browser.perplexity"

            def execute(self, request):
                from gracekelly.core.contracts import ExecutionResult

                return ExecutionResult(
                    adapter_name=self.name,
                    model_id=request.step.model.id,
                    model_display_name=request.step.model.display_name,
                    execution_mode="browser",
                    status=StepStatus.COMPLETED,
                    output_text="browser first",
                    details={"provider": "perplexity"},
                )

        class FakeMistralAdapter:
            name = "api.mistral"

            def __init__(self) -> None:
                self.call_count = 0

            def execute(self, request):
                from gracekelly.core.contracts import ExecutionResult

                self.call_count += 1
                return ExecutionResult(
                    adapter_name=self.name,
                    model_id=request.step.model.id,
                    model_display_name=request.step.model.display_name,
                    execution_mode="api",
                    status=StepStatus.COMPLETED,
                    output_text="api second",
                )

        mistral_adapter = FakeMistralAdapter()
        service = OrchestratorService(
            self.repository,
            execution_router=ExecutionRouter(
                dry_run_adapter=DryRunExecutionAdapter(),
                api_adapters={"mistral": mistral_adapter},
                browser_adapter=FakeBrowserAdapter(),
            ),
        )
        request = OrchestrateRequest(
            prompt="short circuit",
            models=["Kimi K2", "Mistral"],
            dry_run=False,
            quorum=1,
            merge_strategy="first_success",
            cancel_on_quorum=True,
        )

        task = service.submit(request)
        steps = service.list_task_steps(task.task_id)
        events = service.list_task_events(task.task_id)

        self.assertEqual(task.status, "completed")
        self.assertEqual(task.output_text, "browser first")
        self.assertEqual(mistral_adapter.call_count, 0)
        self.assertEqual([step.status for step in steps], ["completed", "cancelled"])
        self.assertEqual([event.sequence_no for event in events], [1, 2, 3])
        self.assertEqual([event.event_type for event in events], ["task.accepted", "step.completed", "task.completed"])
        self.assertEqual(events[1].payload["details"]["provider"], "perplexity")
        self.assertEqual(events[-1].payload["winning_step_index"], 1)
        self.assertEqual(events[-1].payload["cancelled_steps"], [2])
        self.assertEqual(events[-1].payload["cancel_reason"], "quorum_reached")
        self.assertEqual(events[-1].payload["details"]["cancelled_step_count"], 1)
        self.assertEqual(events[-1].payload["details"]["adapter_names"], ["api.mistral", "browser.perplexity"])

    def test_build_step_records_raises_on_plan_result_count_mismatch(self) -> None:
        plan = build_execution_plan(
            OrchestrateRequest(
                prompt="mismatch",
                models=["Kimi K2", "Mistral"],
                dry_run=False,
                merge_strategy="concat",
                cancel_on_quorum=False,
            )
        )
        result = ExecutionResult(
            adapter_name="browser.perplexity",
            model_id=plan.steps[0].model.id,
            model_display_name=plan.steps[0].model.display_name,
            execution_mode=ExecutionMode.BROWSER,
            status=StepStatus.COMPLETED,
            output_text="only one result",
        )

        with self.assertRaises(ValueError):
            self.service._build_step_records("task-mismatch", plan, (result,))

    def test_get_task_raises_key_error_for_missing_task(self) -> None:
        with self.assertRaises(KeyError):
            self.service.get_task("nonexistent-id")

    def test_get_task_raises_storage_unavailable_on_exception(self) -> None:
        class FailingRepository(InMemoryTaskRepository):
            def get(self, task_id: str) -> None:  # type: ignore[override]
                raise RuntimeError("db down")

        service = OrchestratorService(
            FailingRepository(),
            execution_router=ExecutionRouter(dry_run_adapter=DryRunExecutionAdapter()),
        )
        with self.assertRaises(StorageUnavailableError) as ctx:
            service.get_task("t1")
        self.assertIn("get_task", str(ctx.exception))

    def test_list_task_steps_raises_storage_unavailable_on_exception(self) -> None:
        class FailingRepository(InMemoryTaskRepository):
            def list_steps(self, task_id: str) -> list:  # type: ignore[override]
                raise RuntimeError("db down")

        service = OrchestratorService(
            FailingRepository(),
            execution_router=ExecutionRouter(dry_run_adapter=DryRunExecutionAdapter()),
        )
        with self.assertRaises(StorageUnavailableError) as ctx:
            service.list_task_steps("t1")
        self.assertIn("list_task_steps", str(ctx.exception))

    def test_list_recent_tasks_raises_storage_unavailable_on_exception(self) -> None:
        class FailingRepository(InMemoryTaskRepository):
            def list_recent(self, *args, **kwargs) -> list:  # type: ignore[override]
                raise RuntimeError("db down")

        service = OrchestratorService(
            FailingRepository(),
            execution_router=ExecutionRouter(dry_run_adapter=DryRunExecutionAdapter()),
        )
        with self.assertRaises(StorageUnavailableError) as ctx:
            service.list_recent_tasks()
        self.assertIn("list_recent_tasks", str(ctx.exception))

    def test_list_task_events_raises_storage_unavailable_on_exception(self) -> None:
        class FailingRepository(InMemoryTaskRepository):
            def list_events(self, task_id: str) -> list:  # type: ignore[override]
                raise RuntimeError("db down")

        service = OrchestratorService(
            FailingRepository(),
            execution_router=ExecutionRouter(dry_run_adapter=DryRunExecutionAdapter()),
        )
        with self.assertRaises(StorageUnavailableError) as ctx:
            service.list_task_events("t1")
        self.assertIn("list_task_events", str(ctx.exception))

    def test_list_steps_batch_raises_storage_unavailable_on_exception(self) -> None:
        class FailingRepository(InMemoryTaskRepository):
            def list_steps_batch(self, task_ids: list) -> dict:  # type: ignore[override]
                raise RuntimeError("db down")

        service = OrchestratorService(
            FailingRepository(),
            execution_router=ExecutionRouter(dry_run_adapter=DryRunExecutionAdapter()),
        )
        with self.assertRaises(StorageUnavailableError) as ctx:
            service.list_steps_batch(["t1"])
        self.assertIn("list_steps_batch", str(ctx.exception))

    def test_list_events_batch_raises_storage_unavailable_on_exception(self) -> None:
        class FailingRepository(InMemoryTaskRepository):
            def list_events_batch(self, task_ids: list) -> dict:  # type: ignore[override]
                raise RuntimeError("db down")

        service = OrchestratorService(
            FailingRepository(),
            execution_router=ExecutionRouter(dry_run_adapter=DryRunExecutionAdapter()),
        )
        with self.assertRaises(StorageUnavailableError) as ctx:
            service.list_events_batch(["t1"])
        self.assertIn("list_events_batch", str(ctx.exception))

    def test_submit_snapshot_records_retry_of_task_id(self) -> None:
        snapshot = self.service.submit_snapshot(
            OrchestrateRequest(prompt="retry", model="Kimi K2", dry_run=True),
            retry_of_task_id="original-task-id",
        )
        self.assertEqual(snapshot.task.retry_of_task_id, "original-task-id")

    def test_storage_unavailable_error_message_includes_operation(self) -> None:
        err = StorageUnavailableError("my_op", "something broke")
        self.assertIn("my_op", str(err))
        self.assertEqual(err.operation, "my_op")

    def test_build_events_raises_on_plan_result_count_mismatch(self) -> None:
        plan = build_execution_plan(
            OrchestrateRequest(
                prompt="mismatch",
                models=["Kimi K2", "Mistral"],
                dry_run=False,
                merge_strategy="concat",
                cancel_on_quorum=False,
            )
        )
        accepted_at = datetime.now(UTC)
        task = TaskRecord(
            task_id="task-mismatch",
            status=TaskStatus.COMPLETED,
            accepted_at=accepted_at,
            completed_at=accepted_at,
            duration_ms=1,
            prompt="mismatch",
            reasoning=False,
            execution_mode=ExecutionMode.BROWSER,
            dry_run=False,
            model_count=len(plan.steps),
            quorum=plan.quorum,
            merge_strategy=plan.merge_strategy,
            adapter_hint=plan.adapter_hint,
            cancel_on_quorum=plan.cancel_on_quorum,
            output_text="only one result",
        )
        result = ExecutionResult(
            adapter_name="browser.perplexity",
            model_id=plan.steps[0].model.id,
            model_display_name=plan.steps[0].model.display_name,
            execution_mode=ExecutionMode.BROWSER,
            status=StepStatus.COMPLETED,
            output_text="only one result",
        )
        batch_result = ExecutionBatchResult(
            execution_mode=ExecutionMode.BROWSER,
            task_status=TaskStatus.COMPLETED,
            results=(result,),
            output_text="only one result",
        )

        with self.assertRaises(ValueError):
            self.service._build_events(task, plan, batch_result)

    def test_event_result_details_empty_returns_empty_dict(self) -> None:
        result = ExecutionResult(
            adapter_name="browser.perplexity",
            model_id="kimi-k2-5",
            model_display_name="Kimi K2.5",
            execution_mode=ExecutionMode.BROWSER,
            status=StepStatus.COMPLETED,
            details={},
        )
        self.assertEqual(self.service._event_result_details(result), {})

    def test_event_result_details_none_returns_empty_dict(self) -> None:
        result = ExecutionResult(
            adapter_name="browser.perplexity",
            model_id="kimi-k2-5",
            model_display_name="Kimi K2.5",
            execution_mode=ExecutionMode.BROWSER,
            status=StepStatus.COMPLETED,
        )
        self.assertEqual(self.service._event_result_details(result), {})

    def test_event_result_details_non_empty_returns_details_key(self) -> None:
        result = ExecutionResult(
            adapter_name="browser.perplexity",
            model_id="kimi-k2-5",
            model_display_name="Kimi K2.5",
            execution_mode=ExecutionMode.BROWSER,
            status=StepStatus.COMPLETED,
            details={"tokens": 42, "model": "gpt-4"},
        )
        out = self.service._event_result_details(result)
        self.assertIn("details", out)
        self.assertEqual(out["details"]["tokens"], 42)

    def test_event_result_details_non_serializable_coerced_to_string(self) -> None:
        class _Custom:
            def __repr__(self) -> str:
                return "custom-obj"

        result = ExecutionResult(
            adapter_name="browser.perplexity",
            model_id="kimi-k2-5",
            model_display_name="Kimi K2.5",
            execution_mode=ExecutionMode.BROWSER,
            status=StepStatus.COMPLETED,
            details={"obj": _Custom()},
        )
        out = self.service._event_result_details(result)
        self.assertIsInstance(out["details"]["obj"], str)

    def test_event_batch_details_empty_returns_empty_dict(self) -> None:
        batch_result = ExecutionBatchResult(
            execution_mode=ExecutionMode.BROWSER,
            task_status=TaskStatus.COMPLETED,
            results=(),
            output_text="",
            details={},
        )
        self.assertEqual(self.service._event_batch_details(batch_result), {})

    def test_event_batch_details_none_returns_empty_dict(self) -> None:
        batch_result = ExecutionBatchResult(
            execution_mode=ExecutionMode.BROWSER,
            task_status=TaskStatus.COMPLETED,
            results=(),
            output_text="",
        )
        self.assertEqual(self.service._event_batch_details(batch_result), {})

    def test_event_batch_details_non_empty_returns_details_key(self) -> None:
        batch_result = ExecutionBatchResult(
            execution_mode=ExecutionMode.BROWSER,
            task_status=TaskStatus.COMPLETED,
            results=(),
            output_text="",
            details={"quorum_hit": True, "winner_index": 0},
        )
        out = self.service._event_batch_details(batch_result)
        self.assertIn("details", out)
        self.assertTrue(out["details"]["quorum_hit"])


class EventSequenceTests(unittest.TestCase):
    def test_starts_with_no_events(self) -> None:
        seq = _EventSequence("task-1")
        self.assertEqual(seq.events, [])

    def test_append_adds_event(self) -> None:
        seq = _EventSequence("task-1")
        now = datetime.now(UTC)
        seq.append(EventType.TASK_ACCEPTED, now, {"key": "val"})
        self.assertEqual(len(seq.events), 1)

    def test_sequence_no_increments_on_each_append(self) -> None:
        seq = _EventSequence("task-1")
        now = datetime.now(UTC)
        seq.append(EventType.TASK_ACCEPTED, now, {})
        seq.append(EventType.TASK_COMPLETED, now, {})
        self.assertEqual(seq.events[0].sequence_no, 1)
        self.assertEqual(seq.events[1].sequence_no, 2)

    def test_task_id_propagated_to_all_events(self) -> None:
        seq = _EventSequence("task-xyz")
        now = datetime.now(UTC)
        seq.append(EventType.TASK_ACCEPTED, now, {})
        seq.append(EventType.STEP_COMPLETED, now, {})
        for event in seq.events:
            self.assertEqual(event.task_id, "task-xyz")

    def test_payload_stored_on_event(self) -> None:
        seq = _EventSequence("task-1")
        now = datetime.now(UTC)
        seq.append(EventType.TASK_ACCEPTED, now, {"execution_plan": {"steps": []}})
        self.assertEqual(seq.events[0].payload["execution_plan"], {"steps": []})

    def test_event_type_stored(self) -> None:
        seq = _EventSequence("task-1")
        now = datetime.now(UTC)
        seq.append(EventType.TASK_FAILED, now, {})
        self.assertEqual(seq.events[0].event_type, EventType.TASK_FAILED)

    def test_event_ids_are_unique(self) -> None:
        seq = _EventSequence("task-1")
        now = datetime.now(UTC)
        seq.append(EventType.TASK_ACCEPTED, now, {})
        seq.append(EventType.TASK_COMPLETED, now, {})
        ids = {e.event_id for e in seq.events}
        self.assertEqual(len(ids), 2)


if __name__ == "__main__":
    unittest.main()
