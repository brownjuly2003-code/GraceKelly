from __future__ import annotations

import logging
import unittest
from unittest.mock import MagicMock

from gracekelly.core.contracts import (
    ExecutionMode,
    ExecutionResult,
    StepStatus,
)
from gracekelly.core.models import ModelSpec
from gracekelly.core.multi_model import MultiModelExecutor


def _make_spec(
    model_id: str = "test-model",
    provider: str = "test-provider",
) -> ModelSpec:
    return ModelSpec(
        id=model_id,
        display_name=model_id,
        aliases=(model_id,),
        adapter_kind="api",
        provider=provider,
        provider_model_id=model_id,
        timeout_seconds=30,
        expected_latency_class="fast",
        concurrency_limit=4,
    )


def _make_result(
    status: StepStatus = StepStatus.COMPLETED,
    output_text: str | None = "response",
) -> ExecutionResult:
    return ExecutionResult(
        adapter_name="test",
        model_id="test",
        model_display_name="test",
        execution_mode=ExecutionMode.API,
        status=status,
        output_text=output_text,
    )


class TestMultiModelExecutor(unittest.TestCase):
    def test_single_model_success(self) -> None:
        adapter = MagicMock()
        adapter.execute.return_value = _make_result()
        spec = _make_spec()
        executor = MultiModelExecutor({"test-provider": adapter}, [spec])
        result = executor.execute_all("hello")
        self.assertEqual(result.responses, ("response",))
        self.assertEqual(result.model_ids, ("test-model",))
        self.assertEqual(result.failed_models, ())

    def test_multiple_models_success(self) -> None:
        adapter = MagicMock()
        adapter.execute.return_value = _make_result()
        specs = [_make_spec("m1", "p"), _make_spec("m2", "p")]
        executor = MultiModelExecutor({"p": adapter}, specs)
        result = executor.execute_all("hello")
        self.assertEqual(len(result.responses), 2)
        self.assertEqual(result.model_ids, ("m1", "m2"))
        self.assertEqual(result.failed_models, ())

    def test_failed_model_in_failed_list(self) -> None:
        adapter = MagicMock()
        adapter.execute.return_value = _make_result(
            status=StepStatus.FAILED, output_text=None
        )
        spec = _make_spec()
        executor = MultiModelExecutor({"test-provider": adapter}, [spec])
        result = executor.execute_all("hello")
        self.assertEqual(result.responses, ())
        self.assertEqual(result.failed_models, ("test-model",))

    def test_no_adapter_for_provider(self) -> None:
        spec = _make_spec(provider="missing-provider")
        executor = MultiModelExecutor({}, [spec])
        result = executor.execute_all("hello")
        self.assertEqual(result.responses, ())
        self.assertEqual(result.failed_models, ("test-model",))

    def test_exception_during_execute(self) -> None:
        adapter = MagicMock()
        adapter.execute.side_effect = RuntimeError("boom")
        spec = _make_spec()
        executor = MultiModelExecutor({"test-provider": adapter}, [spec])
        with self.assertLogs("gracekelly.core.multi_model", level=logging.WARNING):
            result = executor.execute_all("hello")
        self.assertEqual(result.responses, ())
        self.assertEqual(result.failed_models, ("test-model",))

    def test_empty_model_specs(self) -> None:
        executor = MultiModelExecutor({}, [])
        result = executor.execute_all("hello")
        self.assertEqual(result.responses, ())
        self.assertEqual(result.model_ids, ())
        self.assertEqual(result.failed_models, ())

    def test_model_ids_match_responses(self) -> None:
        adapter_a = MagicMock()
        adapter_a.execute.return_value = _make_result(output_text="resp-a")
        adapter_b = MagicMock()
        adapter_b.execute.side_effect = RuntimeError("fail")
        adapter_c = MagicMock()
        adapter_c.execute.return_value = _make_result(output_text="resp-c")
        specs = [
            _make_spec("m-a", "pa"),
            _make_spec("m-b", "pb"),
            _make_spec("m-c", "pc"),
        ]
        executor = MultiModelExecutor(
            {"pa": adapter_a, "pb": adapter_b, "pc": adapter_c}, specs
        )
        result = executor.execute_all("hello")
        self.assertEqual(result.responses, ("resp-a", "resp-c"))
        self.assertEqual(result.model_ids, ("m-a", "m-c"))
        self.assertEqual(result.failed_models, ("m-b",))

    def test_all_models_fail(self) -> None:
        adapter = MagicMock()
        adapter.execute.side_effect = RuntimeError("fail")
        specs = [_make_spec("m1", "p"), _make_spec("m2", "p")]
        executor = MultiModelExecutor({"p": adapter}, specs)
        result = executor.execute_all("hello")
        self.assertEqual(result.responses, ())
        self.assertEqual(len(result.failed_models), 2)

    def test_completed_but_no_output_text(self) -> None:
        adapter = MagicMock()
        adapter.execute.return_value = _make_result(
            status=StepStatus.COMPLETED, output_text=None
        )
        spec = _make_spec()
        executor = MultiModelExecutor({"test-provider": adapter}, [spec])
        result = executor.execute_all("hello")
        self.assertEqual(result.responses, ())
        self.assertEqual(result.failed_models, ("test-model",))


if __name__ == "__main__":
    unittest.main()
