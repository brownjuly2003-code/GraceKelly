from __future__ import annotations

import unittest
from concurrent.futures import ThreadPoolExecutor

from gracekelly.core.account_pool import Account, AccountPool
from gracekelly.core.circuit_breaker import CircuitBreakerConfig, CircuitBreakingExecutionAdapter
from gracekelly.core.concurrency import ModelConcurrencyGate
from gracekelly.core.contracts import (
    ExecutionAdapter,
    ExecutionBackend,
    ExecutionPlan,
    ExecutionRequest,
    ExecutionResult,
    ExecutionStep,
    FailureCode,
    MergeStrategy,
    StepStatus,
)
from gracekelly.core.models import resolve_model


class ConcurrencyGateStressTests(unittest.TestCase):
    def test_concurrent_acquire_release(self) -> None:
        gate = ModelConcurrencyGate()
        model = resolve_model("Mistral")

        def acquire_release() -> bool:
            if gate.try_acquire(model.id, limit=model.concurrency_limit):
                gate.release(model.id)
                return True
            return False

        with ThreadPoolExecutor(max_workers=20) as pool:
            futures = [pool.submit(acquire_release) for _ in range(100)]
            results = [f.result() for f in futures]

        self.assertTrue(all(results))
        self.assertEqual(gate.snapshot().get(model.id, 0), 0)


class CircuitBreakerStressTests(unittest.TestCase):
    def test_concurrent_execute_with_mixed_results(self) -> None:
        call_count = 0
        results_lock = __import__("threading").Lock()

        class CountingAdapter(ExecutionAdapter):
            name = "test"

            def execute(self, request: ExecutionRequest) -> ExecutionResult:
                nonlocal call_count
                with results_lock:
                    call_count += 1
                    idx = call_count
                if idx % 3 == 0:
                    return ExecutionResult(
                        adapter_name="test", model_id="m", model_display_name="M",
                        execution_mode="api", status=StepStatus.FAILED,
                        failure_code=FailureCode.TIMEOUT, failure_message="slow",
                    )
                return ExecutionResult(
                    adapter_name="test", model_id="m", model_display_name="M",
                    execution_mode="api", status=StepStatus.COMPLETED, output_text="ok",
                )

            def healthcheck(self):
                return {"status": "ok"}

        breaker = CircuitBreakingExecutionAdapter(
            CountingAdapter(),
            config=CircuitBreakerConfig(failure_threshold=5, cooldown_seconds=60),
        )
        model = resolve_model("Mistral")
        step = ExecutionStep(
            model=model, backend=ExecutionBackend.API,
            provider="mistral", provider_model_id="mistral-small-latest", step_index=1,
        )
        plan = ExecutionPlan(
            steps=(step,), quorum=1, merge_strategy=MergeStrategy.FIRST_SUCCESS,
            dry_run=False, adapter_hint="auto", cancel_on_quorum=True,
        )
        request = ExecutionRequest(
            task_id="t1", prompt="test", plan=plan, step=step, reasoning=False,
        )

        with ThreadPoolExecutor(max_workers=10) as pool:
            futures = [pool.submit(breaker.execute, request) for _ in range(30)]
            results = [f.result() for f in futures]

        completed = sum(1 for r in results if r.status == StepStatus.COMPLETED)
        self.assertGreater(completed, 0)


class AccountPoolStressTests(unittest.TestCase):
    def test_concurrent_acquire_release(self) -> None:
        accounts = [
            Account(id=f"a-{i}", credential=f"k-{i}", provider="test", kind="api_key")
            for i in range(5)
        ]
        pool = AccountPool(accounts)

        def use_account() -> bool:
            acct = pool.acquire("test")
            if acct is None:
                return False
            pool.release(acct.id)
            return True

        with ThreadPoolExecutor(max_workers=20) as executor:
            futures = [executor.submit(use_account) for _ in range(100)]
            results = [f.result() for f in futures]

        self.assertTrue(all(results))
        self.assertEqual(pool.available_count("test"), 5)


if __name__ == "__main__":
    unittest.main()
