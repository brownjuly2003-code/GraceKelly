from __future__ import annotations

import threading
import unittest

from gracekelly.adapters.api.mistral import MistralApiAdapter
from gracekelly.adapters.api.openai_compat import OpenAICompatibleApiAdapter
from gracekelly.adapters.dry_run import DryRunExecutionAdapter
from gracekelly.core.contracts import (
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
        extra_headers: dict[str, str] | None = None,
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


class FakeOpenAICompatibleAdapter(OpenAICompatibleApiAdapter):
    def __init__(self) -> None:
        super().__init__(api_key="test-key", base_url="https://example.test/v1", timeout_seconds=1.0)
        self.last_timeout_seconds: float | None = None

    def _post_json(
        self,
        path: str,
        payload: dict[str, object],
        *,
        timeout_seconds: float,
        extra_headers: dict[str, str] | None = None,
    ) -> dict[str, object]:
        self.last_timeout_seconds = timeout_seconds
        return {
            "choices": [
                {
                    "message": {
                        "content": [
                            {"type": "text", "text": "stubbed openai response"},
                        ]
                    }
                }
            ]
        }


def build_request(task_id: str, prompt: str, plan: ExecutionPlan) -> ExecutionRequest:
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

    def test_dry_run_returns_merged_output_text(self) -> None:
        router = ExecutionRouter(dry_run_adapter=DryRunExecutionAdapter())
        plan = build_execution_plan(
            OrchestrateRequest(
                prompt="dry run output",
                model="Mistral",
                dry_run=True,
            )
        )

        result = router.execute(
            task_id="task-1b",
            prompt="dry run output",
            plan=plan,
            reasoning=False,
            metadata={},
        )

        self.assertEqual(result.task_status, TaskStatus.COMPLETED)
        self.assertIsNotNone(result.output_text)
        assert result.output_text is not None
        self.assertIn("[dry-run]", result.output_text)

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

    def test_openai_compat_adapter_completes_when_registered(self) -> None:
        adapter = FakeOpenAICompatibleAdapter()
        router = ExecutionRouter(
            dry_run_adapter=DryRunExecutionAdapter(),
            api_adapters={"openai": adapter},
        )
        plan = build_execution_plan(
            OrchestrateRequest(
                prompt="call api",
                model="GPT-5.4 API",
                dry_run=False,
            )
        )

        result = router.execute(
            task_id="task-2c",
            prompt="call api",
            plan=plan,
            reasoning=True,
            metadata={},
        )

        self.assertEqual(result.task_status, TaskStatus.COMPLETED)
        self.assertEqual(result.details["adapter_names"], ["api.openai"])
        self.assertEqual(result.output_text, "stubbed openai response")
        self.assertEqual(adapter.last_timeout_seconds, 60.0)

    def test_openai_compat_adapter_uses_per_model_timeout_hint(self) -> None:
        adapter = FakeOpenAICompatibleAdapter()
        plan = build_execution_plan(
            OrchestrateRequest(
                prompt="call api",
                model="GPT-5.4 API",
                dry_run=False,
                reasoning=True,
            )
        )

        result = adapter.execute(build_request("task-2d", "call api", plan))

        self.assertEqual(result.status, StepStatus.COMPLETED)
        self.assertEqual(adapter.last_timeout_seconds, 60.0)
        self.assertEqual(result.details["timeout_seconds"], 60.0)

    def test_concat_runs_all_steps_when_short_circuit_is_disabled(self) -> None:
        class FakeBrowserAdapter(ExecutionAdapter):
            name = "browser.perplexity"

            def execute(self, request: ExecutionRequest) -> ExecutionResult:
                return ExecutionResult(
                    adapter_name=self.name,
                    model_id=request.step.model.id,
                    model_display_name=request.step.model.display_name,
                    execution_mode=ExecutionMode.BROWSER,
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
                merge_strategy=MergeStrategy.CONCAT,
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
                )

        class FakeApiAdapter(ExecutionAdapter):
            name = "api.mistral"

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
                merge_strategy=MergeStrategy.FIRST_SUCCESS,
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
        class BlockingBrowserAdapter(ExecutionAdapter):
            name = "browser.perplexity"

            def __init__(self) -> None:
                self.started = threading.Event()
                self.release_execution = threading.Event()
                self.call_count = 0

            def execute(self, request: ExecutionRequest) -> ExecutionResult:
                self.call_count += 1
                self.started.set()
                self.release_execution.wait(timeout=2.0)
                return ExecutionResult(
                    adapter_name=self.name,
                    model_id=request.step.model.id,
                    model_display_name=request.step.model.display_name,
                    execution_mode=ExecutionMode.BROWSER,
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
        first_result_holder: dict[str, ExecutionBatchResult] = {}

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

        assert result.failure_code is not None
        self.assertEqual(result.failure_code.value, "provider_unavailable")
        self.assertEqual(result.status, StepStatus.FAILED)


class OpenAICompatibleAdapterTests(unittest.TestCase):
    def test_missing_api_key_returns_provider_unavailable(self) -> None:
        adapter = OpenAICompatibleApiAdapter(api_key=None, base_url="https://example.test/v1", timeout_seconds=1.0)
        plan = build_execution_plan(
            OrchestrateRequest(
                prompt="missing key",
                model="GPT-5.4 API",
                dry_run=False,
                reasoning=True,
            )
        )

        result = adapter.execute(build_request("task-3b", "missing key", plan))

        assert result.failure_code is not None
        self.assertEqual(result.failure_code.value, "provider_unavailable")
        self.assertEqual(result.status, StepStatus.FAILED)


if __name__ == "__main__":
    unittest.main()
