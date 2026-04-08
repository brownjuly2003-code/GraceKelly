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

_MODEL = ModelSpec(
    id="mistral-small",
    display_name="Mistral Small",
    aliases=("Mistral",),
    adapter_kind="api",
    provider="mistral",
    provider_model_id="mistral-small-latest",
    timeout_seconds=30,
    expected_latency_class="fast",
    concurrency_limit=4,
    reasoning_capable=False,
)

_STEP = ExecutionStep(
    model=_MODEL,
    backend=ExecutionBackend.API,
    provider="mistral",
    provider_model_id="mistral-small-latest",
    step_index=1,
)

_PLAN = ExecutionPlan(
    steps=(_STEP,),
    quorum=1,
    merge_strategy=MergeStrategy.FIRST_SUCCESS,
    dry_run=True,
    adapter_hint=AdapterHint.AUTO,
    cancel_on_quorum=True,
)


def _make_request(*, reasoning: bool = False) -> ExecutionRequest:
    return ExecutionRequest(
        task_id="t1",
        prompt="What is 2+2?",
        plan=_PLAN,
        step=_STEP,
        reasoning=reasoning,
    )


class DryRunAdapterExecuteTests(unittest.TestCase):
    def setUp(self) -> None:
        self.adapter = DryRunExecutionAdapter()

    def test_status_is_completed(self) -> None:
        result = self.adapter.execute(_make_request())
        self.assertEqual(result.status, StepStatus.COMPLETED)

    def test_execution_mode_is_dry_run(self) -> None:
        result = self.adapter.execute(_make_request())
        self.assertEqual(result.execution_mode, ExecutionMode.DRY_RUN)

    def test_model_id_matches_step(self) -> None:
        result = self.adapter.execute(_make_request())
        self.assertEqual(result.model_id, "mistral-small")

    def test_model_display_name_matches_step(self) -> None:
        result = self.adapter.execute(_make_request())
        self.assertEqual(result.model_display_name, "Mistral Small")

    def test_adapter_name_is_dry_run(self) -> None:
        result = self.adapter.execute(_make_request())
        self.assertEqual(result.adapter_name, "dry-run")

    def test_details_simulated_true(self) -> None:
        result = self.adapter.execute(_make_request())
        self.assertTrue(result.details["simulated"])

    def test_details_reasoning_false(self) -> None:
        result = self.adapter.execute(_make_request(reasoning=False))
        self.assertFalse(result.details["reasoning"])

    def test_details_reasoning_true_preserved(self) -> None:
        result = self.adapter.execute(_make_request(reasoning=True))
        self.assertTrue(result.details["reasoning"])

    def test_details_active_model_display_name(self) -> None:
        result = self.adapter.execute(_make_request())
        self.assertEqual(result.details["active_model"], "Mistral Small")

    def test_details_requested_models_contains_display_name(self) -> None:
        result = self.adapter.execute(_make_request())
        self.assertIn("Mistral Small", result.details["requested_models"])

    def test_no_failure_code(self) -> None:
        result = self.adapter.execute(_make_request())
        self.assertIsNone(result.failure_code)

    def test_no_output_text(self) -> None:
        result = self.adapter.execute(_make_request())
        self.assertEqual(result.output_text, "[dry-run] Simulated response for: What is 2+2?")

    def test_duration_ms_is_zero(self) -> None:
        result = self.adapter.execute(_make_request())
        self.assertEqual(result.duration_ms, 0)


class DryRunAdapterMultiStepTests(unittest.TestCase):
    def test_multi_step_plan_lists_all_models(self) -> None:
        model2 = ModelSpec(
            id="kimi-k2-5",
            display_name="Kimi K2",
            aliases=("Kimi K2.5",),
            adapter_kind="browser",
            provider="perplexity",
            provider_model_id="Kimi K2.5",
            timeout_seconds=60,
            expected_latency_class="slow",
            concurrency_limit=1,
        )
        step2 = ExecutionStep(
            model=model2,
            backend=ExecutionBackend.BROWSER,
            provider="perplexity",
            provider_model_id="Kimi K2.5",
            step_index=2,
        )
        plan = ExecutionPlan(
            steps=(_STEP, step2),
            quorum=1,
            merge_strategy=MergeStrategy.FIRST_SUCCESS,
            dry_run=True,
            adapter_hint=AdapterHint.AUTO,
            cancel_on_quorum=True,
        )
        request = ExecutionRequest(
            task_id="t1",
            prompt="compare",
            plan=plan,
            step=_STEP,
            reasoning=False,
        )
        result = DryRunExecutionAdapter().execute(request)
        self.assertIn("Mistral Small", result.details["requested_models"])
        self.assertIn("Kimi K2", result.details["requested_models"])
        self.assertEqual(len(result.details["requested_models"]), 2)


class DryRunAdapterHealthcheckTests(unittest.TestCase):
    def setUp(self) -> None:
        self.adapter = DryRunExecutionAdapter()

    def test_status_is_ok(self) -> None:
        self.assertEqual(self.adapter.healthcheck()["status"], "ok")

    def test_adapter_name_in_healthcheck(self) -> None:
        self.assertEqual(self.adapter.healthcheck()["adapter_name"], "dry-run")

    def test_simulated_true_in_healthcheck(self) -> None:
        self.assertTrue(self.adapter.healthcheck()["simulated"])


if __name__ == "__main__":
    unittest.main()
