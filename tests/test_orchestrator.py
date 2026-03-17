from __future__ import annotations

import unittest

from gracekelly.adapters.dry_run import DryRunExecutionAdapter
from gracekelly.core.contracts import StepStatus
from gracekelly.core.orchestrator import OrchestratorService, StorageUnavailableError
from gracekelly.core.router import ExecutionRouter
from gracekelly.schemas import OrchestrateRequest
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


if __name__ == "__main__":
    unittest.main()
