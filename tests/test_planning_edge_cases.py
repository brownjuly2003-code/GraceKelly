from __future__ import annotations

import unittest

from gracekelly.core.contracts import AdapterHint, MergeStrategy
from gracekelly.core.planning import build_execution_plan
from gracekelly.schemas import OrchestrateRequest


class PlanningEdgeCasesTests(unittest.TestCase):
    def test_quorum_clamped_when_exceeds_model_count(self) -> None:
        """quorum > len(steps) → clamped to len(steps)."""
        request = OrchestrateRequest(
            prompt="test",
            models=["Mistral", "sonar"],
            quorum=8,  # max allowed by schema, but only 2 models
        )
        plan = build_execution_plan(request)
        self.assertEqual(plan.quorum, 2)

    def test_quorum_equals_models_with_concat_and_cancel_on_quorum_ok(self) -> None:
        """concat + cancel_on_quorum=True is valid when quorum covers all models."""
        request = OrchestrateRequest(
            prompt="test",
            models=["Mistral", "sonar"],
            merge_strategy=MergeStrategy.CONCAT,
            quorum=2,
            cancel_on_quorum=True,
        )
        plan = build_execution_plan(request)
        self.assertEqual(plan.quorum, 2)

    def test_concat_cancel_on_quorum_false_partial_quorum_ok(self) -> None:
        """concat + cancel_on_quorum=False is always valid regardless of quorum."""
        request = OrchestrateRequest(
            prompt="test",
            models=["Mistral", "sonar"],
            merge_strategy=MergeStrategy.CONCAT,
            quorum=1,
            cancel_on_quorum=False,
        )
        plan = build_execution_plan(request)
        self.assertEqual(plan.quorum, 1)

    def test_step_indexes_start_at_one(self) -> None:
        """Steps are indexed from 1, not 0."""
        request = OrchestrateRequest(
            prompt="test",
            models=["sonar", "Mistral"],
        )
        plan = build_execution_plan(request)
        self.assertEqual(plan.steps[0].step_index, 1)
        self.assertEqual(plan.steps[1].step_index, 2)

    def test_reasoning_capable_model_with_reasoning_true_succeeds(self) -> None:
        """A reasoning-capable model with reasoning=True should not raise."""
        request = OrchestrateRequest(
            prompt="think through this",
            model="Kimi K2.5",
            reasoning=True,
        )
        plan = build_execution_plan(request)
        self.assertTrue(plan.steps[0].model.reasoning_capable)

    def test_single_model_plan_has_one_step(self) -> None:
        request = OrchestrateRequest(prompt="hello", model="sonar")
        plan = build_execution_plan(request)
        self.assertEqual(len(plan.steps), 1)

    def test_plan_preserves_dry_run_flag(self) -> None:
        request = OrchestrateRequest(prompt="test", model="sonar", dry_run=True)
        plan = build_execution_plan(request)
        self.assertTrue(plan.dry_run)

    def test_plan_preserves_cancel_on_quorum(self) -> None:
        request = OrchestrateRequest(
            prompt="test", model="sonar", cancel_on_quorum=False,
        )
        plan = build_execution_plan(request)
        self.assertFalse(plan.cancel_on_quorum)

    def test_adapter_hint_auto_allows_any_backend(self) -> None:
        """adapter_hint=AUTO should not raise even for browser-backed models."""
        request = OrchestrateRequest(
            prompt="test",
            model="Kimi K2",
            adapter_hint=AdapterHint.AUTO,
        )
        plan = build_execution_plan(request)
        self.assertEqual(plan.steps[0].backend.value, "browser")


if __name__ == "__main__":
    unittest.main()
