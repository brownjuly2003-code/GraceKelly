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
            merge_strategy="concat",
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
            OrchestrateRequest(
                prompt="bad adapter hint",
                model="Mistral",
                adapter_hint="desktop",
            )

    def test_rejects_unknown_merge_strategy(self) -> None:
        with self.assertRaises(ValueError):
            OrchestrateRequest(
                prompt="bad merge strategy",
                model="Mistral",
                merge_strategy="fanout",
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
            merge_strategy="concat",
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


if __name__ == "__main__":
    unittest.main()
