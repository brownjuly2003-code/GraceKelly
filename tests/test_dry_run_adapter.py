from __future__ import annotations

import unittest

from gracekelly.adapters.dry_run import DryRunExecutionAdapter
from gracekelly.core.contracts import (
    AdapterHint,
    ExecutionBackend,
    ExecutionMode,
    ExecutionPlan,
    ExecutionRequest,
    ExecutionStep,
    MergeStrategy,
    StepStatus,
)
from gracekelly.core.models import ModelSpec


def _make_model(model_id: str = "gpt-4o", display_name: str = "GPT-4o") -> ModelSpec:
    return ModelSpec(
        id=model_id,
        display_name=display_name,
        aliases=(),
        adapter_kind="api",
        provider="openai",
        provider_model_id=model_id,
        timeout_seconds=60,
        expected_latency_class="fast",
        concurrency_limit=4,
    )


def _make_step(model: ModelSpec) -> ExecutionStep:
    return ExecutionStep(
        model=model,
        backend=ExecutionBackend.API,
        provider="openai",
        provider_model_id=model.provider_model_id,
        step_index=0,
    )


def _make_request(
    model: ModelSpec,
    *,
    extra_models: list[ModelSpec] | None = None,
    reasoning: bool = False,
) -> ExecutionRequest:
    all_models = [model] + (extra_models or [])
    steps = tuple(_make_step(m) for m in all_models)
    plan = ExecutionPlan(
        steps=steps,
        quorum=1,
        merge_strategy=MergeStrategy.FIRST_SUCCESS,
        dry_run=True,
        adapter_hint=AdapterHint.AUTO,
        cancel_on_quorum=False,
    )
    return ExecutionRequest(
        task_id="task-001",
        prompt="What is 2+2?",
        plan=plan,
        step=steps[0],
        reasoning=reasoning,
    )


class DryRunAdapterTests(unittest.TestCase):
    def setUp(self) -> None:
        self.adapter = DryRunExecutionAdapter()

    def test_name(self) -> None:
        self.assertEqual(self.adapter.name, "dry-run")

    def test_execute_returns_completed_status(self) -> None:
        result = self.adapter.execute(_make_request(_make_model()))
        self.assertEqual(result.status, StepStatus.COMPLETED)

    def test_execute_returns_dry_run_mode(self) -> None:
        result = self.adapter.execute(_make_request(_make_model()))
        self.assertEqual(result.execution_mode, ExecutionMode.DRY_RUN)

    def test_execute_adapter_name_in_result(self) -> None:
        result = self.adapter.execute(_make_request(_make_model()))
        self.assertEqual(result.adapter_name, "dry-run")

    def test_execute_model_id_from_step(self) -> None:
        model = _make_model("claude-3-5-sonnet", "Claude 3.5 Sonnet")
        result = self.adapter.execute(_make_request(model))
        self.assertEqual(result.model_id, "claude-3-5-sonnet")
        self.assertEqual(result.model_display_name, "Claude 3.5 Sonnet")

    def test_execute_details_simulated_flag(self) -> None:
        result = self.adapter.execute(_make_request(_make_model()))
        self.assertIs(result.details["simulated"], True)

    def test_execute_details_active_model(self) -> None:
        model = _make_model("gpt-4o", "GPT-4o")
        result = self.adapter.execute(_make_request(model))
        self.assertEqual(result.details["active_model"], "GPT-4o")

    def test_execute_details_requested_models_single(self) -> None:
        model = _make_model("gpt-4o", "GPT-4o")
        result = self.adapter.execute(_make_request(model))
        self.assertEqual(result.details["requested_models"], ["GPT-4o"])

    def test_execute_details_requested_models_multi(self) -> None:
        m1 = _make_model("gpt-4o", "GPT-4o")
        m2 = _make_model("claude-3-5-sonnet", "Claude 3.5 Sonnet")
        result = self.adapter.execute(_make_request(m1, extra_models=[m2]))
        self.assertIn("GPT-4o", result.details["requested_models"])
        self.assertIn("Claude 3.5 Sonnet", result.details["requested_models"])

    def test_execute_reasoning_flag_passed(self) -> None:
        result = self.adapter.execute(_make_request(_make_model(), reasoning=True))
        self.assertIs(result.details["reasoning"], True)

    def test_execute_no_failure(self) -> None:
        result = self.adapter.execute(_make_request(_make_model()))
        self.assertIsNone(result.failure_code)
        self.assertFalse(result.is_failure)

    def test_healthcheck_returns_ok(self) -> None:
        hc = self.adapter.healthcheck()
        self.assertEqual(hc["status"], "ok")

    def test_healthcheck_adapter_name(self) -> None:
        hc = self.adapter.healthcheck()
        self.assertEqual(hc["adapter_name"], "dry-run")

    def test_healthcheck_simulated_flag(self) -> None:
        hc = self.adapter.healthcheck()
        self.assertIs(hc["simulated"], True)


if __name__ == "__main__":
    unittest.main()
