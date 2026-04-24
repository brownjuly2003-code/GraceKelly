from __future__ import annotations

import unittest
from datetime import UTC, datetime
from typing import Any
from unittest.mock import MagicMock, patch

from gracekelly.adapters.dry_run import DryRunExecutionAdapter
from gracekelly.config import Settings
from gracekelly.core.complexity import assess_complexity
from gracekelly.core.contracts import (
    AdapterHint,
    EventType,
    ExecutionAdapter,
    ExecutionBatchResult,
    ExecutionMode,
    ExecutionPlan,
    ExecutionRequest,
    ExecutionResult,
    FailureCode,
    MergeStrategy,
    StepStatus,
    TaskStatus,
)
from gracekelly.core.event_builder import _EventSequence
from gracekelly.core.orchestrator import (
    OrchestratorService,
    StorageUnavailableError,
)
from gracekelly.core.planning import build_execution_plan
from gracekelly.core.router import ExecutionRouter
from gracekelly.core.session_context import build_session_context
from gracekelly.schemas import OrchestrateRequest
from gracekelly.storage.base import TaskEventRecord, TaskRecord, TaskStepRecord
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
        class FakeOpenAIAdapter(ExecutionAdapter):
            name = "api.openai"

            def execute(self, request: ExecutionRequest) -> ExecutionResult:
                return ExecutionResult(
                    adapter_name=self.name,
                    model_id=request.step.model.id,
                    model_display_name=request.step.model.display_name,
                    execution_mode=ExecutionMode.API,
                    status=StepStatus.COMPLETED,
                    output_text="api result",
                )

        service = OrchestratorService(
            self.repository,
            execution_router=ExecutionRouter(
                dry_run_adapter=DryRunExecutionAdapter(),
                api_adapters={"openai": FakeOpenAIAdapter()},
            ),
        )
        snapshot = service.submit_snapshot(
            OrchestrateRequest(
                prompt="snapshot",
                model="GPT-5.4 API",
                dry_run=False,
            )
        )

        self.assertEqual(snapshot.task.status, "completed")
        self.assertEqual(len(snapshot.steps), 1)
        self.assertEqual(snapshot.steps[0].status, "completed")

    def test_submit_snapshot_persists_accepted_task_before_execution(self) -> None:
        class InspectingRouter(ExecutionRouter):
            def __init__(self, repository: InMemoryTaskRepository) -> None:
                super().__init__(dry_run_adapter=DryRunExecutionAdapter())
                self._repository = repository
                self.observed_task: TaskRecord | None = None
                self.observed_events: list[TaskEventRecord] = []

            def execute(
                self,
                *,
                task_id: str,
                prompt: str,
                plan: ExecutionPlan,
                reasoning: bool,
                metadata: dict[str, object],
            ) -> ExecutionBatchResult:
                self.observed_task = self._repository.get(task_id)
                self.observed_events = self._repository.list_events(task_id)
                return ExecutionBatchResult(
                    execution_mode=ExecutionMode.DRY_RUN,
                    task_status=TaskStatus.COMPLETED,
                    results=(),
                    output_text="accepted first",
                )

        repository = InMemoryTaskRepository()
        router = InspectingRouter(repository)
        service = OrchestratorService(repository, execution_router=router)

        snapshot = service.submit_snapshot(
            OrchestrateRequest(
                prompt="accepted first",
                model="Kimi K2",
                dry_run=True,
            )
        )

        assert router.observed_task is not None
        self.assertEqual(router.observed_task.status, TaskStatus.ACCEPTED)
        self.assertEqual([event.event_type for event in router.observed_events], [EventType.TASK_ACCEPTED])
        self.assertEqual(snapshot.task.status, TaskStatus.COMPLETED)

    def test_non_dry_run_api_request_can_complete(self) -> None:
        class FakeOpenAIAdapter(ExecutionAdapter):
            name = "api.openai"

            def execute(self, request: ExecutionRequest) -> ExecutionResult:
                return ExecutionResult(
                    adapter_name=self.name,
                    model_id=request.step.model.id,
                    model_display_name=request.step.model.display_name,
                    execution_mode=ExecutionMode.API,
                    status=StepStatus.COMPLETED,
                    output_text="api result",
                    details={"provider": "openai"},
                )

        self.service = OrchestratorService(
            self.repository,
            execution_router=ExecutionRouter(
                dry_run_adapter=DryRunExecutionAdapter(),
                api_adapters={"openai": FakeOpenAIAdapter()},
            ),
        )

        request = OrchestrateRequest(
            prompt="real execution later",
            model="GPT-5.4 API",
            dry_run=False,
        )

        task = self.service.submit(request)
        steps = self.service.list_task_steps(task.task_id)

        self.assertEqual(task.status, "completed")
        self.assertEqual(task.execution_mode, "api")
        self.assertFalse(task.dry_run)
        self.assertEqual(task.output_text, "api result")
        self.assertEqual(len(steps), 1)
        self.assertEqual(steps[0].model_id, "gpt-5-4-api")
        self.assertEqual(steps[0].status, "completed")
        events = self.service.list_task_events(task.task_id)
        self.assertEqual(
            [item.event_type for item in events],
            ["task.accepted", "step.completed", "task.completed"],
        )
        self.assertEqual(events[1].payload["details"]["provider"], "openai")
        self.assertEqual(events[-1].payload["details"]["adapter_names"], ["api.openai"])
        self.assertEqual(events[-1].payload["details"]["completed_step_count"], 1)
        self.assertEqual(events[-1].payload["details"]["failed_step_count"], 0)

    def test_submit_snapshot_executes_browser_only_live_plan_inline(self) -> None:
        class FakeBrowserAdapter(ExecutionAdapter):
            name = "browser.perplexity"

            def execute(self, request: ExecutionRequest) -> ExecutionResult:
                return ExecutionResult(
                    adapter_name=self.name,
                    model_id=request.step.model.id,
                    model_display_name=request.step.model.display_name,
                    execution_mode=ExecutionMode.BROWSER,
                    status=StepStatus.COMPLETED,
                    output_text="browser inline result",
                )

        class InlineBrowserRouter(ExecutionRouter):
            def __init__(self) -> None:
                super().__init__(
                    dry_run_adapter=DryRunExecutionAdapter(),
                    browser_adapter=FakeBrowserAdapter(),
                )
                self.execute_calls = 0
                self.dispatch_calls = 0

            def execute(
                self,
                *,
                task_id: str,
                prompt: str,
                plan: ExecutionPlan,
                reasoning: bool,
                metadata: dict[str, object],
            ) -> ExecutionBatchResult:
                self.execute_calls += 1
                raise AssertionError("browser-only live plans should execute inline")

            def _dispatch_step(self, step: Any, request: ExecutionRequest) -> ExecutionResult:
                self.dispatch_calls += 1
                return super()._dispatch_step(step, request)

        router = InlineBrowserRouter()
        service = OrchestratorService(self.repository, execution_router=router)

        snapshot = service.submit_snapshot(
            OrchestrateRequest(
                prompt="browser inline",
                model="Kimi K2",
                dry_run=False,
            )
        )

        self.assertEqual(snapshot.task.status, TaskStatus.COMPLETED)
        self.assertEqual(snapshot.task.execution_mode, ExecutionMode.BROWSER)
        self.assertEqual(snapshot.task.output_text, "browser inline result")
        self.assertEqual(len(snapshot.steps), 1)
        self.assertEqual(snapshot.steps[0].status, StepStatus.COMPLETED)
        self.assertEqual(router.execute_calls, 0)
        self.assertEqual(router.dispatch_calls, 1)

    def test_complex_prompt_triggers_decomposition(self) -> None:
        complex_prompt = (
            "Compare distributed tracing approaches and also explain deployment trade-offs, "
            "additionally outline the monitoring implications for incident response."
        )
        self.assertTrue(assess_complexity(complex_prompt).should_decompose)

        class FakeOpenAIAdapter(ExecutionAdapter):
            name = "api.openai"

            def __init__(self) -> None:
                self.prompts: list[str] = []

            def execute(self, request: ExecutionRequest) -> ExecutionResult:
                self.prompts.append(request.prompt)
                if request.prompt.startswith("Break this question into independent sub-questions."):
                    output_text = (
                        '["What are the tracing approaches?",'
                        ' "What are the deployment trade-offs and monitoring implications?"]'
                    )
                elif request.prompt == "What are the tracing approaches?":
                    output_text = "Tracing answer"
                elif request.prompt == "What are the deployment trade-offs and monitoring implications?":
                    output_text = "Trade-off answer"
                elif request.prompt.startswith("Combine these answers into one comprehensive response."):
                    output_text = "Final synthesized answer"
                else:
                    output_text = "Unexpected prompt"
                return ExecutionResult(
                    adapter_name=self.name,
                    model_id=request.step.model.id,
                    model_display_name=request.step.model.display_name,
                    execution_mode=ExecutionMode.API,
                    status=StepStatus.COMPLETED,
                    output_text=output_text,
                )

        class TrackingRouter(ExecutionRouter):
            def __init__(self, adapter: ExecutionAdapter) -> None:
                super().__init__(
                    dry_run_adapter=DryRunExecutionAdapter(),
                    api_adapters={"openai": adapter},
                )
                self.execute_calls = 0

            def execute(
                self,
                *,
                task_id: str,
                prompt: str,
                plan: ExecutionPlan,
                reasoning: bool,
                metadata: dict[str, object],
            ) -> ExecutionBatchResult:
                self.execute_calls += 1
                return super().execute(
                    task_id=task_id,
                    prompt=prompt,
                    plan=plan,
                    reasoning=reasoning,
                    metadata=metadata,
                )

        adapter = FakeOpenAIAdapter()
        router = TrackingRouter(adapter)
        service = OrchestratorService(self.repository, execution_router=router)

        snapshot = service.submit_snapshot(
            OrchestrateRequest(
                prompt=complex_prompt,
                model="GPT-5.4 API",
                dry_run=False,
            )
        )

        self.assertTrue(snapshot.task.was_decomposed)
        self.assertEqual(snapshot.task.subtask_count, 2)
        self.assertEqual(snapshot.task.output_text, "Final synthesized answer")
        self.assertEqual(router.execute_calls, 0)
        self.assertEqual(len(adapter.prompts), 4)

    def test_simple_prompt_skips_decomposition(self) -> None:
        router = MagicMock()
        router.execute.return_value = ExecutionBatchResult(
            execution_mode=ExecutionMode.API,
            task_status=TaskStatus.COMPLETED,
            results=(
                ExecutionResult(
                    adapter_name="api.openai",
                    model_id="gpt-5-4-api",
                    model_display_name="GPT-5.4 API",
                    execution_mode=ExecutionMode.API,
                    status=StepStatus.COMPLETED,
                    output_text="simple answer",
                ),
            ),
            output_text="simple answer",
        )
        service = OrchestratorService(self.repository, execution_router=router)

        with patch("gracekelly.core.orchestrator.execute_decomposed", side_effect=AssertionError):
            snapshot = service.submit_snapshot(
                OrchestrateRequest(
                    prompt="What is 2+2?",
                    model="GPT-5.4 API",
                    dry_run=False,
                )
            )

        self.assertFalse(snapshot.task.was_decomposed)
        self.assertEqual(snapshot.task.subtask_count, 0)
        self.assertEqual(snapshot.task.output_text, "simple answer")
        router.execute.assert_called_once()

    def test_decompose_false_disables_decomposition(self) -> None:
        router = MagicMock()
        router.execute.return_value = ExecutionBatchResult(
            execution_mode=ExecutionMode.API,
            task_status=TaskStatus.COMPLETED,
            results=(
                ExecutionResult(
                    adapter_name="api.openai",
                    model_id="gpt-5-4-api",
                    model_display_name="GPT-5.4 API",
                    execution_mode=ExecutionMode.API,
                    status=StepStatus.COMPLETED,
                    output_text="standard execution",
                ),
            ),
            output_text="standard execution",
        )
        service = OrchestratorService(self.repository, execution_router=router)

        with patch("gracekelly.core.orchestrator.execute_decomposed", side_effect=AssertionError):
            snapshot = service.submit_snapshot(
                OrchestrateRequest(
                    prompt=(
                        "Compare architectural approaches and also explain deployment trade-offs, "
                        "additionally cover operational risks."
                    ),
                    model="GPT-5.4 API",
                    dry_run=False,
                    decompose=False,
                )
            )

        self.assertFalse(snapshot.task.was_decomposed)
        self.assertEqual(snapshot.task.subtask_count, 0)
        self.assertEqual(snapshot.task.output_text, "standard execution")
        router.execute.assert_called_once()

    def test_dry_run_skips_decomposition(self) -> None:
        router = MagicMock()
        router.execute.return_value = ExecutionBatchResult(
            execution_mode=ExecutionMode.DRY_RUN,
            task_status=TaskStatus.COMPLETED,
            results=(),
            output_text="dry-run answer",
        )
        service = OrchestratorService(self.repository, execution_router=router)

        with patch("gracekelly.core.orchestrator.execute_decomposed", side_effect=AssertionError):
            snapshot = service.submit_snapshot(
                OrchestrateRequest(
                    prompt=(
                        "Compare testing strategies and also explain delivery trade-offs, "
                        "additionally describe rollback considerations."
                    ),
                    model="GPT-5.4 API",
                    dry_run=True,
                )
            )

        self.assertFalse(snapshot.task.was_decomposed)
        self.assertEqual(snapshot.task.subtask_count, 0)
        self.assertEqual(snapshot.task.output_text, "dry-run answer")
        router.execute.assert_called_once()

    def test_failed_task_event_carries_batch_execution_details(self) -> None:
        task = self.service.submit(
            OrchestrateRequest(
                prompt="missing adapter",
                model="GPT-5.4 API",
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
        self.assertEqual(events[-1].payload["details"]["adapter_names"], ["api.openai"])
        self.assertEqual(events[-1].payload["details"]["failed_step_count"], 1)
        self.assertEqual(events[-1].payload["details"]["failure_codes"], ["provider_unavailable"])

    def test_submit_snapshot_generates_trace_id_for_auth_failed_task_without_metadata(self) -> None:
        class FakeBrowserAdapter(ExecutionAdapter):
            name = "browser.perplexity"

            def execute(self, request: ExecutionRequest) -> ExecutionResult:
                return ExecutionResult(
                    adapter_name=self.name,
                    model_id=request.step.model.id,
                    model_display_name=request.step.model.display_name,
                    execution_mode=ExecutionMode.BROWSER,
                    status=StepStatus.FAILED,
                    failure_code=FailureCode.AUTH_FAILED,
                    failure_message="Perplexity sign-in overlay blocked prompt submission.",
                    details={"provider": "perplexity"},
                )

        service = OrchestratorService(
            self.repository,
            execution_router=ExecutionRouter(
                dry_run_adapter=DryRunExecutionAdapter(),
                browser_adapter=FakeBrowserAdapter(),
            ),
        )

        snapshot = service.submit_snapshot(
            OrchestrateRequest(
                prompt="browser auth",
                model="Kimi K2",
                dry_run=False,
            )
        )

        self.assertEqual(snapshot.task.status, TaskStatus.FAILED)
        self.assertEqual(snapshot.task.failure_code, FailureCode.AUTH_FAILED)
        self.assertIn("trace_id", snapshot.task.metadata)
        self.assertTrue(snapshot.task.metadata["trace_id"])
        persisted = self.repository.get(snapshot.task.task_id)
        assert persisted is not None
        self.assertEqual(persisted.metadata["trace_id"], snapshot.task.metadata["trace_id"])

    def test_submit_raises_storage_unavailable_when_persistence_fails(self) -> None:
        class FailingRepository(InMemoryTaskRepository):
            def save_task_with_steps(self, task: TaskRecord, steps: list[TaskStepRecord]) -> None:
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

    def test_submit_raises_storage_unavailable_when_final_snapshot_replace_fails(self) -> None:
        class ReplaceFailingRepository(InMemoryTaskRepository):
            def replace_task_snapshot(
                self,
                task: TaskRecord,
                steps: list[TaskStepRecord],
                events: list[TaskEventRecord],
            ) -> None:
                raise RuntimeError("final write offline")

        service = OrchestratorService(
            ReplaceFailingRepository(),
            execution_router=ExecutionRouter(dry_run_adapter=DryRunExecutionAdapter()),
        )

        with self.assertRaises(StorageUnavailableError) as ctx:
            service.submit(
                OrchestrateRequest(
                    prompt="replace failure",
                    model="Kimi K2",
                    dry_run=True,
                )
            )

        self.assertIn("replace_task_snapshot", str(ctx.exception))

    def test_submit_logs_warning_when_event_persistence_fails(self) -> None:
        class EventFailingRepository(InMemoryTaskRepository):
            def append_event(self, event: TaskEventRecord) -> None:
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
        class FakeBrowserAdapter(ExecutionAdapter):
            name = "browser.perplexity"

            def execute(self, request: ExecutionRequest) -> ExecutionResult:
                return ExecutionResult(
                    adapter_name=self.name,
                    model_id=request.step.model.id,
                    model_display_name=request.step.model.display_name,
                    execution_mode=ExecutionMode.BROWSER,
                    status=StepStatus.COMPLETED,
                    output_text="browser first",
                    details={"provider": "perplexity"},
                )

        class FakeOpenAIAdapter(ExecutionAdapter):
            name = "api.openai"

            def __init__(self) -> None:
                self.call_count = 0

            def execute(self, request: ExecutionRequest) -> ExecutionResult:
                self.call_count += 1
                return ExecutionResult(
                    adapter_name=self.name,
                    model_id=request.step.model.id,
                    model_display_name=request.step.model.display_name,
                    execution_mode=ExecutionMode.API,
                    status=StepStatus.COMPLETED,
                    output_text="api second",
                )

        openai_adapter = FakeOpenAIAdapter()
        service = OrchestratorService(
            self.repository,
            execution_router=ExecutionRouter(
                dry_run_adapter=DryRunExecutionAdapter(),
                api_adapters={"openai": openai_adapter},
                browser_adapter=FakeBrowserAdapter(),
            ),
        )
        request = OrchestrateRequest(
            prompt="short circuit",
            models=["Kimi K2", "GPT-5.4 API"],
            dry_run=False,
            quorum=1,
            merge_strategy=MergeStrategy.FIRST_SUCCESS,
            cancel_on_quorum=True,
        )

        task = service.submit(request)
        steps = service.list_task_steps(task.task_id)
        events = service.list_task_events(task.task_id)

        self.assertEqual(task.status, "completed")
        self.assertEqual(task.output_text, "browser first")
        self.assertEqual(openai_adapter.call_count, 0)
        self.assertEqual([step.status for step in steps], ["completed", "cancelled"])
        self.assertEqual([event.sequence_no for event in events], [1, 2, 3])
        self.assertEqual([event.event_type for event in events], ["task.accepted", "step.completed", "task.completed"])
        self.assertEqual(events[1].payload["details"]["provider"], "perplexity")
        self.assertEqual(events[-1].payload["winning_step_index"], 1)
        self.assertEqual(events[-1].payload["cancelled_steps"], [2])
        self.assertEqual(events[-1].payload["cancel_reason"], "quorum_reached")
        self.assertEqual(events[-1].payload["details"]["cancelled_step_count"], 1)
        self.assertEqual(events[-1].payload["details"]["adapter_names"], ["api.openai", "browser.perplexity"])

    def test_build_step_records_raises_on_plan_result_count_mismatch(self) -> None:
        plan = build_execution_plan(
            OrchestrateRequest(
                prompt="mismatch",
                models=["Kimi K2", "GPT-5.4 API"],
                dry_run=False,
                merge_strategy=MergeStrategy.CONCAT,
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
            self.service._event_builder.build_step_records("task-mismatch", plan, (result,))

    def test_get_task_raises_key_error_for_missing_task(self) -> None:
        with self.assertRaises(KeyError):
            self.service.get_task("nonexistent-id")

    def test_get_task_raises_storage_unavailable_on_exception(self) -> None:
        class FailingRepository(InMemoryTaskRepository):
            def get(self, task_id: str) -> None:
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
            def list_steps(self, task_id: str) -> list[TaskStepRecord]:
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
            def list_recent(self, *args: Any, **kwargs: Any) -> list[TaskRecord]:
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
            def list_events(self, task_id: str) -> list[TaskEventRecord]:
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
            def list_steps_batch(self, task_ids: list[str]) -> dict[str, list[TaskStepRecord]]:
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
            def list_events_batch(self, task_ids: list[str]) -> dict[str, list[TaskEventRecord]]:
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

    def test_session_chain_builds_context_from_previous_turns(self) -> None:
        class CapturingRouter(ExecutionRouter):
            def __init__(self) -> None:
                super().__init__(dry_run_adapter=DryRunExecutionAdapter())
                self.observed_prompt: str | None = None

            def execute(
                self,
                *,
                task_id: str,
                prompt: str,
                plan: ExecutionPlan,
                reasoning: bool,
                metadata: dict[str, object],
            ) -> ExecutionBatchResult:
                self.observed_prompt = prompt
                return ExecutionBatchResult(
                    execution_mode=ExecutionMode.DRY_RUN,
                    task_status=TaskStatus.COMPLETED,
                    results=(),
                    output_text="ok",
                )

        router = CapturingRouter()
        service = OrchestratorService(self.repository, execution_router=router)
        session_id = "session-1"
        accepted_at = datetime(2026, 4, 11, 10, 0, tzinfo=UTC)
        for idx in range(3):
            self.repository.save_task_with_steps(
                TaskRecord(
                    task_id=f"existing-task-{idx + 1}",
                    status=TaskStatus.COMPLETED,
                    accepted_at=accepted_at.replace(minute=idx),
                    completed_at=accepted_at.replace(minute=idx),
                    duration_ms=10,
                    prompt=f"question {idx + 1}",
                    reasoning=False,
                    execution_mode=ExecutionMode.API,
                    dry_run=False,
                    model_count=1,
                    quorum=1,
                    merge_strategy=MergeStrategy.FIRST_SUCCESS,
                    adapter_hint=AdapterHint.AUTO,
                    cancel_on_quorum=True,
                    output_text=f"answer {idx + 1}",
                    session_id=session_id,
                ),
                [],
            )

        snapshot = service.submit_snapshot(
            OrchestrateRequest(
                prompt="question 4",
                model="Kimi K2",
                dry_run=True,
                session_id=session_id,
            )
        )

        self.assertEqual(
            router.observed_prompt,
            (
                "[Turn 1]\nUser: question 1\nAssistant: answer 1\n\n"
                "[Turn 2]\nUser: question 2\nAssistant: answer 2\n\n"
                "[Turn 3]\nUser: question 3\nAssistant: answer 3\n\n"
                "[Current]\nUser: question 4"
            ),
        )
        self.assertEqual(snapshot.task.prompt, "question 4")

    def test_session_chain_respects_window_limit(self) -> None:
        class CapturingRouter(ExecutionRouter):
            def __init__(self) -> None:
                super().__init__(dry_run_adapter=DryRunExecutionAdapter())
                self.observed_prompt: str | None = None

            def execute(
                self,
                *,
                task_id: str,
                prompt: str,
                plan: ExecutionPlan,
                reasoning: bool,
                metadata: dict[str, object],
            ) -> ExecutionBatchResult:
                self.observed_prompt = prompt
                return ExecutionBatchResult(
                    execution_mode=ExecutionMode.DRY_RUN,
                    task_status=TaskStatus.COMPLETED,
                    results=(),
                    output_text="ok",
                )

        repository = InMemoryTaskRepository()
        router = CapturingRouter()
        service = OrchestratorService(
            repository,
            execution_router=router,
            settings=Settings(context_window_turns=20),
        )
        session_id = "session-1"
        accepted_at = datetime(2026, 4, 11, 10, 0, tzinfo=UTC)
        for idx in range(25):
            repository.save_task_with_steps(
                TaskRecord(
                    task_id=f"existing-task-{idx + 1}",
                    status=TaskStatus.COMPLETED,
                    accepted_at=accepted_at.replace(minute=idx),
                    completed_at=accepted_at.replace(minute=idx),
                    duration_ms=10,
                    prompt=f"question {idx + 1}",
                    reasoning=False,
                    execution_mode=ExecutionMode.API,
                    dry_run=False,
                    model_count=1,
                    quorum=1,
                    merge_strategy=MergeStrategy.FIRST_SUCCESS,
                    adapter_hint=AdapterHint.AUTO,
                    cancel_on_quorum=True,
                    output_text=f"answer {idx + 1}",
                    session_id=session_id,
                ),
                [],
            )

        snapshot = service.submit_snapshot(
            OrchestrateRequest(
                prompt="question 26",
                model="Kimi K2",
                dry_run=True,
                session_id=session_id,
            )
        )

        assert router.observed_prompt is not None
        self.assertIn("[Turn 1]\nUser: question 6\nAssistant: answer 6", router.observed_prompt)
        self.assertIn("[Turn 20]\nUser: question 25\nAssistant: answer 25", router.observed_prompt)
        self.assertNotIn("[Turn 1]\nUser: question 1\nAssistant: answer 1", router.observed_prompt)
        self.assertEqual(snapshot.task.prompt, "question 26")

    def test_no_session_id_skips_context_lookup(self) -> None:
        class CapturingRepository(InMemoryTaskRepository):
            def __init__(self) -> None:
                super().__init__()
                self.list_by_session_calls = 0

            def list_by_session(self, session_id: str, *, limit: int) -> list[TaskRecord]:
                self.list_by_session_calls += 1
                return super().list_by_session(session_id, limit=limit)

        repository = CapturingRepository()
        service = OrchestratorService(
            repository,
            execution_router=ExecutionRouter(dry_run_adapter=DryRunExecutionAdapter()),
        )

        snapshot = service.submit_snapshot(
            OrchestrateRequest(
                prompt="standalone question",
                model="Kimi K2",
                dry_run=True,
            )
        )

        self.assertEqual(repository.list_by_session_calls, 0)
        self.assertEqual(snapshot.task.prompt, "standalone question")

    def test_list_recent_tasks_passes_prompt_contains_to_repository(self) -> None:
        class CapturingRepository(InMemoryTaskRepository):
            def __init__(self) -> None:
                super().__init__()
                self.prompt_contains: str | None = None

            def list_recent(
                self,
                limit: int,
                *,
                status: Any = None,
                execution_mode: Any = None,
                dry_run: Any = None,
                failure_code: Any = None,
                before: Any = None,
                prompt_contains: str | None = None,
            ) -> list[TaskRecord]:
                self.prompt_contains = prompt_contains
                return super().list_recent(
                    limit,
                    status=status,
                    execution_mode=execution_mode,
                    dry_run=dry_run,
                    failure_code=failure_code,
                    before=before,
                    prompt_contains=prompt_contains,
                )

        repository = CapturingRepository()
        service = OrchestratorService(
            repository,
            execution_router=ExecutionRouter(dry_run_adapter=DryRunExecutionAdapter()),
        )

        service.list_recent_tasks(prompt_contains="alpha")

        self.assertEqual(repository.prompt_contains, "alpha")

    def test_storage_unavailable_error_message_includes_operation(self) -> None:
        err = StorageUnavailableError("my_op", "something broke")
        self.assertIn("my_op", str(err))
        self.assertEqual(err.operation, "my_op")

    def test_build_events_raises_on_plan_result_count_mismatch(self) -> None:
        plan = build_execution_plan(
            OrchestrateRequest(
                prompt="mismatch",
                models=["Kimi K2", "GPT-5.4 API"],
                dry_run=False,
                merge_strategy=MergeStrategy.CONCAT,
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
            self.service._event_builder.build_events(task, plan, batch_result)

    def test_event_result_details_empty_returns_empty_dict(self) -> None:
        result = ExecutionResult(
            adapter_name="browser.perplexity",
            model_id="kimi-k2-5",
            model_display_name="Kimi K2.5",
            execution_mode=ExecutionMode.BROWSER,
            status=StepStatus.COMPLETED,
            details={},
        )
        self.assertEqual(self.service._event_builder._event_result_details(result), {})

    def test_event_result_details_none_returns_empty_dict(self) -> None:
        result = ExecutionResult(
            adapter_name="browser.perplexity",
            model_id="kimi-k2-5",
            model_display_name="Kimi K2.5",
            execution_mode=ExecutionMode.BROWSER,
            status=StepStatus.COMPLETED,
        )
        self.assertEqual(self.service._event_builder._event_result_details(result), {})

    def test_event_result_details_non_empty_returns_details_key(self) -> None:
        result = ExecutionResult(
            adapter_name="browser.perplexity",
            model_id="kimi-k2-5",
            model_display_name="Kimi K2.5",
            execution_mode=ExecutionMode.BROWSER,
            status=StepStatus.COMPLETED,
            details={"tokens": 42, "model": "gpt-4"},
        )
        out = self.service._event_builder._event_result_details(result)
        self.assertIn("details", out)
        details = out.get("details")
        assert isinstance(details, dict)
        self.assertEqual(details["tokens"], 42)

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
        out = self.service._event_builder._event_result_details(result)
        details = out.get("details")
        assert isinstance(details, dict)
        self.assertIsInstance(details["obj"], str)

    def test_event_batch_details_empty_returns_empty_dict(self) -> None:
        batch_result = ExecutionBatchResult(
            execution_mode=ExecutionMode.BROWSER,
            task_status=TaskStatus.COMPLETED,
            results=(),
            output_text="",
            details={},
        )
        self.assertEqual(self.service._event_builder._event_batch_details(batch_result), {})

    def test_event_batch_details_none_returns_empty_dict(self) -> None:
        batch_result = ExecutionBatchResult(
            execution_mode=ExecutionMode.BROWSER,
            task_status=TaskStatus.COMPLETED,
            results=(),
            output_text="",
        )
        self.assertEqual(self.service._event_builder._event_batch_details(batch_result), {})

    def test_event_batch_details_non_empty_returns_details_key(self) -> None:
        batch_result = ExecutionBatchResult(
            execution_mode=ExecutionMode.BROWSER,
            task_status=TaskStatus.COMPLETED,
            results=(),
            output_text="",
            details={"quorum_hit": True, "winner_index": 0},
        )
        out = self.service._event_builder._event_batch_details(batch_result)
        self.assertIn("details", out)
        details = out.get("details")
        assert isinstance(details, dict)
        self.assertTrue(details["quorum_hit"])

    def test_build_session_context_trims_history_to_max_chars(self) -> None:
        repository = InMemoryTaskRepository()
        session_id = "session-trim"
        accepted_at = datetime(2026, 4, 11, 10, 0, tzinfo=UTC)
        for idx in range(2):
            repository.save_task_with_steps(
                TaskRecord(
                    task_id=f"existing-task-{idx + 1}",
                    status=TaskStatus.COMPLETED,
                    accepted_at=accepted_at.replace(minute=idx),
                    completed_at=accepted_at.replace(minute=idx),
                    duration_ms=10,
                    prompt=f"question {idx + 1}",
                    reasoning=False,
                    execution_mode=ExecutionMode.API,
                    dry_run=False,
                    model_count=1,
                    quorum=1,
                    merge_strategy=MergeStrategy.FIRST_SUCCESS,
                    adapter_hint=AdapterHint.AUTO,
                    cancel_on_quorum=True,
                    output_text=f"answer {idx + 1}",
                    session_id=session_id,
                ),
                [],
            )

        prompt = build_session_context(
            repository,
            session_id,
            "question 3",
            Settings(context_window_turns=20, max_context_chars=60),
        )

        self.assertLessEqual(len(prompt.split("\n\n[Current]\nUser:")[0]), 60)
        self.assertTrue(prompt.endswith("[Current]\nUser: question 3"))


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
