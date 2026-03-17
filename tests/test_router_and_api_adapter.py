from __future__ import annotations

import threading
import unittest

from gracekelly.adapters.api.mistral import MistralApiAdapter
from gracekelly.adapters.dry_run import DryRunExecutionAdapter
from gracekelly.core.contracts import ExecutionMode, ExecutionRequest, ExecutionResult, FailureCode, StepStatus, TaskStatus
from gracekelly.core.planning import build_execution_plan
from gracekelly.core.router import ExecutionRouter
from gracekelly.schemas import OrchestrateRequest


class FakeMistralAdapter(MistralApiAdapter):
    def __init__(self) -> None:
        super().__init__(api_key="test-key", base_url="https://example.test/v1", timeout_seconds=1.0)
        self.last_timeout_seconds: float | None = None

    def _post_json(
        self,
        path: str,
        payload: dict[str, object],
        *,
        timeout_seconds: float,
    ) -> dict[str, object]:
        self.last_timeout_seconds = timeout_seconds
        return {
            "choices": [
                {
                    "message": {
                        "content": "stubbed mistral response"
                    }
                }
            ]
        }


def build_request(task_id: str, prompt: str, plan) -> ExecutionRequest:
    return ExecutionRequest(
        task_id=task_id,
        prompt=prompt,
        plan=plan,
        step=plan.steps[0],
        reasoning=False,
        metadata={},
    )


class ExecutionRouterTests(unittest.TestCase):
    def test_dry_run_multi_model_returns_completed(self) -> None:
        router = ExecutionRouter(dry_run_adapter=DryRunExecutionAdapter())
        plan = build_execution_plan(
            OrchestrateRequest(
                prompt="dry run",
                models=["Kimi K2", "Mistral"],
                dry_run=True,
                quorum=1,
            )
        )

        result = router.execute(
            task_id="task-1",
            prompt="dry run",
            plan=plan,
            reasoning=False,
            metadata={},
        )

        self.assertEqual(result.task_status, TaskStatus.COMPLETED)
        self.assertEqual(result.execution_mode, "dry-run")
        self.assertEqual(len(result.results), 2)
        self.assertTrue(all(item.status == StepStatus.COMPLETED for item in result.results))

    def test_api_adapter_completes_when_registered(self) -> None:
        adapter = FakeMistralAdapter()
        router = ExecutionRouter(
            dry_run_adapter=DryRunExecutionAdapter(),
            api_adapters={"mistral": adapter},
        )
        plan = build_execution_plan(
            OrchestrateRequest(
                prompt="call api",
                model="Mistral",
                dry_run=False,
            )
        )

        result = router.execute(
            task_id="task-2",
            prompt="call api",
            plan=plan,
            reasoning=False,
            metadata={},
        )

        self.assertEqual(result.task_status, TaskStatus.COMPLETED)
        self.assertEqual(result.details["adapter_names"], ["api.mistral"])
        self.assertEqual(result.output_text, "stubbed mistral response")
        self.assertEqual(adapter.last_timeout_seconds, 30.0)

    def test_api_adapter_uses_per_model_timeout_hint(self) -> None:
        adapter = FakeMistralAdapter()
        plan = build_execution_plan(
            OrchestrateRequest(
                prompt="call api",
                model="Mistral",
                dry_run=False,
            )
        )

        result = adapter.execute(build_request("task-2b", "call api", plan))

        self.assertEqual(result.status, StepStatus.COMPLETED)
        self.assertEqual(adapter.last_timeout_seconds, 30.0)
        self.assertEqual(result.details["timeout_seconds"], 30.0)

    def test_concat_runs_all_steps_when_short_circuit_is_disabled(self) -> None:
        class FakeBrowserAdapter:
            name = "browser.perplexity"

            def execute(self, request):
                return ExecutionResult(
                    adapter_name=self.name,
                    model_id=request.step.model.id,
                    model_display_name=request.step.model.display_name,
                    execution_mode="browser",
                    status=StepStatus.COMPLETED,
                    output_text="browser result",
                )

        router = ExecutionRouter(
            dry_run_adapter=DryRunExecutionAdapter(),
            api_adapters={"mistral": FakeMistralAdapter()},
            browser_adapter=FakeBrowserAdapter(),
        )
        plan = build_execution_plan(
            OrchestrateRequest(
                prompt="concat execution",
                models=["Kimi K2", "Mistral"],
                dry_run=False,
                merge_strategy="concat",
                quorum=1,
                cancel_on_quorum=False,
            )
        )

        result = router.execute(
            task_id="task-4",
            prompt="concat execution",
            plan=plan,
            reasoning=False,
            metadata={},
        )

        self.assertEqual(result.task_status, TaskStatus.COMPLETED)
        self.assertEqual(result.execution_mode, "mixed")
        self.assertEqual(result.output_text, "browser result\n\nstubbed mistral response")
        self.assertEqual(result.details["adapter_names"], ["api.mistral", "browser.perplexity"])
        self.assertEqual(result.details["winning_step_index"], None)
        self.assertEqual(result.details["cancelled_steps"], [])
        self.assertTrue(all(item.status == StepStatus.COMPLETED for item in result.results))

    def test_first_success_short_circuits_remaining_steps(self) -> None:
        class FakeBrowserAdapter:
            name = "browser.perplexity"

            def execute(self, request):
                return ExecutionResult(
                    adapter_name=self.name,
                    model_id=request.step.model.id,
                    model_display_name=request.step.model.display_name,
                    execution_mode="browser",
                    status=StepStatus.COMPLETED,
                    output_text="browser first",
                )

        class FakeApiAdapter:
            name = "api.mistral"

            def __init__(self) -> None:
                self.call_count = 0

            def execute(self, request):
                self.call_count += 1
                return ExecutionResult(
                    adapter_name=self.name,
                    model_id=request.step.model.id,
                    model_display_name=request.step.model.display_name,
                    execution_mode="api",
                    status=StepStatus.COMPLETED,
                    output_text="api second",
                )

        api_adapter = FakeApiAdapter()
        router = ExecutionRouter(
            dry_run_adapter=DryRunExecutionAdapter(),
            api_adapters={"mistral": api_adapter},
            browser_adapter=FakeBrowserAdapter(),
        )
        plan = build_execution_plan(
            OrchestrateRequest(
                prompt="first success",
                models=["Kimi K2", "Mistral"],
                dry_run=False,
                merge_strategy="first_success",
                quorum=1,
                cancel_on_quorum=True,
            )
        )

        result = router.execute(
            task_id="task-5",
            prompt="first success",
            plan=plan,
            reasoning=False,
            metadata={},
        )

        self.assertEqual(result.task_status, TaskStatus.COMPLETED)
        self.assertEqual(result.output_text, "browser first")
        self.assertEqual(api_adapter.call_count, 0)
        self.assertEqual(result.details["winning_step_index"], 1)
        self.assertEqual(result.details["winning_model_id"], "kimi-k2-5")
        self.assertEqual(result.details["cancelled_steps"], [2])
        self.assertEqual(result.details["cancel_reason"], "quorum_reached")
        self.assertEqual([item.status for item in result.results], [StepStatus.COMPLETED, StepStatus.CANCELLED])

    def test_concurrency_limit_rejects_parallel_execution_for_same_model(self) -> None:
        class BlockingBrowserAdapter:
            name = "browser.perplexity"

            def __init__(self) -> None:
                self.started = threading.Event()
                self.release_execution = threading.Event()
                self.call_count = 0

            def execute(self, request):
                self.call_count += 1
                self.started.set()
                self.release_execution.wait(timeout=2.0)
                return ExecutionResult(
                    adapter_name=self.name,
                    model_id=request.step.model.id,
                    model_display_name=request.step.model.display_name,
                    execution_mode="browser",
                    status=StepStatus.COMPLETED,
                    output_text="browser result",
                )

        adapter = BlockingBrowserAdapter()
        router = ExecutionRouter(
            dry_run_adapter=DryRunExecutionAdapter(),
            browser_adapter=adapter,
        )
        plan = build_execution_plan(
            OrchestrateRequest(
                prompt="concurrency test",
                model="Kimi K2",
                dry_run=False,
            )
        )
        first_result_holder: dict[str, object] = {}

        def run_first() -> None:
            first_result_holder["result"] = router.execute(
                task_id="task-concurrency-1",
                prompt="concurrency test",
                plan=plan,
                reasoning=False,
                metadata={},
            )

        first_thread = threading.Thread(target=run_first)
        first_thread.start()
        self.assertTrue(adapter.started.wait(timeout=1.0))

        second_result = router.execute(
            task_id="task-concurrency-2",
            prompt="concurrency test",
            plan=plan,
            reasoning=False,
            metadata={},
        )

        self.assertEqual(second_result.task_status, TaskStatus.FAILED)
        self.assertEqual(second_result.results[0].status, StepStatus.FAILED)
        self.assertEqual(second_result.results[0].failure_code, FailureCode.RATE_LIMITED)
        self.assertEqual(second_result.results[0].details["concurrency_limit"], 1)
        self.assertEqual(adapter.call_count, 1)

        adapter.release_execution.set()
        first_thread.join(timeout=2.0)
        self.assertFalse(first_thread.is_alive())

        first_result = first_result_holder["result"]
        self.assertEqual(first_result.task_status, TaskStatus.COMPLETED)

        third_result = router.execute(
            task_id="task-concurrency-3",
            prompt="concurrency test",
            plan=plan,
            reasoning=False,
            metadata={},
        )

        self.assertEqual(third_result.task_status, TaskStatus.COMPLETED)
        self.assertEqual(adapter.call_count, 2)

    def test_aggregate_raises_on_plan_result_count_mismatch(self) -> None:
        router = ExecutionRouter(dry_run_adapter=DryRunExecutionAdapter())
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
            router._aggregate(plan, (result,))


class MistralAdapterTests(unittest.TestCase):
    def test_missing_api_key_returns_provider_unavailable(self) -> None:
        adapter = MistralApiAdapter(api_key=None, base_url="https://example.test/v1", timeout_seconds=1.0)
        plan = build_execution_plan(
            OrchestrateRequest(
                prompt="missing key",
                model="Mistral",
                dry_run=False,
            )
        )

        result = adapter.execute(build_request("task-3", "missing key", plan))

        self.assertEqual(result.failure_code.value, "provider_unavailable")
        self.assertEqual(result.status, StepStatus.FAILED)


if __name__ == "__main__":
    unittest.main()
