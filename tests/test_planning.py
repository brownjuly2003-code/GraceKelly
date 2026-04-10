from __future__ import annotations

import unittest

from gracekelly.core.contracts import AdapterHint, MergeStrategy
from gracekelly.core.planning import build_execution_plan
from gracekelly.schemas import OrchestrateRequest


class ExecutionPlanningTests(unittest.TestCase):
    def test_builds_multi_model_plan_with_mixed_backends(self) -> None:
        request = OrchestrateRequest(
            prompt="compare options",
            models=["Kimi K2", "Mistral"],
            dry_run=False,
            quorum=2,
            merge_strategy=MergeStrategy.CONCAT,
        )

        plan = build_execution_plan(request)

        self.assertEqual(len(plan.steps), 2)
        self.assertEqual(plan.steps[0].backend.value, "browser")
        self.assertEqual(plan.steps[1].backend.value, "api")
        self.assertEqual(plan.quorum, 2)
        self.assertEqual(plan.merge_strategy, MergeStrategy.CONCAT)

    def test_rejects_conflicting_adapter_hint(self) -> None:
        request = OrchestrateRequest(
            prompt="api only request",
            model="Kimi K2",
            adapter_hint=AdapterHint.API,
        )

        with self.assertRaises(ValueError):
            build_execution_plan(request)

    def test_rejects_unknown_adapter_hint(self) -> None:
        with self.assertRaises(ValueError):
            OrchestrateRequest.model_validate(
                {
                    "prompt": "bad adapter hint",
                    "model": "Mistral",
                    "adapter_hint": "desktop",
                }
            )

    def test_rejects_unknown_merge_strategy(self) -> None:
        with self.assertRaises(ValueError):
            OrchestrateRequest.model_validate(
                {
                    "prompt": "bad merge strategy",
                    "model": "Mistral",
                    "merge_strategy": "fanout",
                }
            )

    def test_rejects_duplicate_models_after_canonicalization(self) -> None:
        request = OrchestrateRequest(
            prompt="duplicate canonical model",
            models=["Kimi K2", "Kimi K2.5"],
        )

        with self.assertRaises(ValueError):
            build_execution_plan(request)

    def test_rejects_concat_with_short_circuiting_quorum(self) -> None:
        request = OrchestrateRequest(
            prompt="truncated concat",
            models=["Kimi K2", "Mistral"],
            merge_strategy=MergeStrategy.CONCAT,
            quorum=1,
            cancel_on_quorum=True,
        )

        with self.assertRaises(ValueError):
            build_execution_plan(request)

    def test_rejects_reasoning_for_unsupported_model(self) -> None:
        request = OrchestrateRequest(
            prompt="reasoning on unsupported model",
            model="Mistral",
            reasoning=True,
        )

        with self.assertRaises(ValueError):
            build_execution_plan(request)

    def test_rejects_non_json_serializable_metadata(self) -> None:
        with self.assertRaises(ValueError):
            OrchestrateRequest(
                prompt="bad metadata",
                model="Mistral",
                metadata={"bad": object()},
            )


class ExecutionPlanningStructureTests(unittest.TestCase):
    """Tests for the structural output of build_execution_plan."""

    def test_single_model_produces_one_step(self) -> None:
        plan = build_execution_plan(OrchestrateRequest(prompt="Q", model="Mistral"))
        self.assertEqual(len(plan.steps), 1)
        self.assertEqual(plan.steps[0].model.id, "mistral-small")

    def test_step_indices_are_one_based(self) -> None:
        plan = build_execution_plan(
            OrchestrateRequest(prompt="Q", models=["Kimi K2", "Mistral"])
        )
        self.assertEqual(plan.steps[0].step_index, 1)
        self.assertEqual(plan.steps[1].step_index, 2)

    def test_api_model_backend_is_api(self) -> None:
        plan = build_execution_plan(OrchestrateRequest(prompt="Q", model="Mistral"))
        self.assertEqual(plan.steps[0].backend.value, "api")

    def test_provider_copied_to_step(self) -> None:
        plan = build_execution_plan(OrchestrateRequest(prompt="Q", model="Mistral"))
        self.assertEqual(plan.steps[0].provider, "mistral")

    def test_dry_run_passed_through_to_plan(self) -> None:
        plan = build_execution_plan(
            OrchestrateRequest(prompt="Q", model="Mistral", dry_run=True)
        )
        self.assertTrue(plan.dry_run)

    def test_quorum_capped_at_step_count(self) -> None:
        plan = build_execution_plan(
            OrchestrateRequest(prompt="Q", models=["Kimi K2", "Mistral"], quorum=5)
        )
        self.assertEqual(plan.quorum, 2)

    def test_cancel_on_quorum_passed_through(self) -> None:
        plan = build_execution_plan(
            OrchestrateRequest(prompt="Q", model="Mistral", cancel_on_quorum=False)
        )
        self.assertFalse(plan.cancel_on_quorum)


class ExecutionPlanningPositiveEdgeCasesTests(unittest.TestCase):
    """Positive edge cases that must NOT raise."""

    def test_concat_with_cancel_on_quorum_false_ok(self) -> None:
        plan = build_execution_plan(
            OrchestrateRequest(
                prompt="Q",
                models=["Kimi K2", "Mistral"],
                merge_strategy=MergeStrategy.CONCAT,
                cancel_on_quorum=False,
                quorum=1,
            )
        )
        self.assertEqual(plan.merge_strategy, MergeStrategy.CONCAT)

    def test_concat_quorum_covers_all_steps_ok(self) -> None:
        """CONCAT + cancel_on_quorum=True is fine when quorum == len(steps)."""
        plan = build_execution_plan(
            OrchestrateRequest(
                prompt="Q",
                models=["Kimi K2", "Mistral"],
                merge_strategy=MergeStrategy.CONCAT,
                cancel_on_quorum=True,
                quorum=2,
            )
        )
        self.assertEqual(plan.merge_strategy, MergeStrategy.CONCAT)

    def test_reasoning_with_reasoning_capable_model_ok(self) -> None:
        plan = build_execution_plan(
            OrchestrateRequest(prompt="Q", model="GPT-5.4 API", reasoning=True)
        )
        self.assertEqual(len(plan.steps), 1)

    def test_adapter_hint_api_with_api_model_ok(self) -> None:
        plan = build_execution_plan(
            OrchestrateRequest(prompt="Q", model="Mistral", adapter_hint=AdapterHint.API)
        )
        self.assertEqual(len(plan.steps), 1)

    def test_adapter_hint_browser_with_browser_model_ok(self) -> None:
        plan = build_execution_plan(
            OrchestrateRequest(prompt="Q", model="Kimi K2", adapter_hint=AdapterHint.BROWSER)
        )
        self.assertEqual(len(plan.steps), 1)

    def test_adapter_hint_auto_passes_any_backend(self) -> None:
        for model_name in ["Mistral", "Kimi K2"]:
            with self.subTest(model=model_name):
                plan = build_execution_plan(
                    OrchestrateRequest(
                        prompt="Q", model=model_name, adapter_hint=AdapterHint.AUTO
                    )
                )
                self.assertEqual(len(plan.steps), 1)


if __name__ == "__main__":
    unittest.main()
