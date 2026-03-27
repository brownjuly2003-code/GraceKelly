from __future__ import annotations

import unittest

from gracekelly.core.account_pool import Account, AccountPool
from gracekelly.core.account_pool_manager import (
    AccountPoolManager,
)


def _make_pool(n: int = 1, provider: str = "openai") -> AccountPool:
    accounts = [
        Account(
            id=f"acc-{i}",
            credential=f"key-{i}",
            provider=provider,
            kind="api_key",
        )
        for i in range(n)
    ]
    return AccountPool(accounts)


class TestAccountPoolManager(unittest.TestCase):
    def test_successful_execution(self) -> None:
        pool = _make_pool()
        mgr = AccountPoolManager(pool)

        def execute_fn(prompt: str, api_key: str) -> str:
            return f"response to {prompt}"

        result = mgr.execute_with_account("openai", execute_fn, "hello")
        self.assertTrue(result.success)
        self.assertEqual(result.response, "response to hello")
        self.assertEqual(result.account_id, "acc-0")

    def test_account_released_after_success(self) -> None:
        pool = _make_pool()
        mgr = AccountPoolManager(pool)
        mgr.execute_with_account("openai", lambda p, k: "ok", "test")
        self.assertEqual(pool.available_count("openai"), 1)

    def test_failed_execution(self) -> None:
        pool = _make_pool()
        mgr = AccountPoolManager(pool)

        def failing_fn(prompt: str, api_key: str) -> str:
            raise RuntimeError("boom")

        result = mgr.execute_with_account("openai", failing_fn, "test")
        self.assertFalse(result.success)
        self.assertEqual(result.response, "Execution failed")
        self.assertEqual(result.account_id, "acc-0")

    def test_account_marked_cooldown_after_failure(self) -> None:
        pool = _make_pool()
        mgr = AccountPoolManager(pool, cooldown_seconds=300.0)

        def failing_fn(prompt: str, api_key: str) -> str:
            raise ValueError("fail")

        mgr.execute_with_account("openai", failing_fn, "test")
        self.assertEqual(pool.available_count("openai"), 0)

    def test_no_accounts_available(self) -> None:
        pool = AccountPool()
        mgr = AccountPoolManager(pool)
        result = mgr.execute_with_account("openai", lambda p, k: "ok", "test")
        self.assertFalse(result.success)
        self.assertEqual(result.account_id, "")
        self.assertEqual(result.response, "No accounts available")

    def test_execute_fn_receives_prompt_and_credential(self) -> None:
        pool = _make_pool()
        mgr = AccountPoolManager(pool)
        captured: list[tuple[str, str]] = []

        def capture_fn(prompt: str, api_key: str) -> str:
            captured.append((prompt, api_key))
            return "done"

        mgr.execute_with_account("openai", capture_fn, "my prompt")
        self.assertEqual(len(captured), 1)
        self.assertEqual(captured[0][0], "my prompt")
        self.assertEqual(captured[0][1], "key-0")

    def test_available_count(self) -> None:
        pool = _make_pool(3)
        mgr = AccountPoolManager(pool)
        self.assertEqual(mgr.available_count("openai"), 3)
        self.assertEqual(mgr.available_count("anthropic"), 0)

    def test_pool_property(self) -> None:
        pool = _make_pool()
        mgr = AccountPoolManager(pool)
        self.assertIs(mgr.pool, pool)

    def test_multiple_sequential_executions(self) -> None:
        pool = _make_pool(2)
        mgr = AccountPoolManager(pool)
        r1 = mgr.execute_with_account("openai", lambda p, k: "r1", "p1")
        r2 = mgr.execute_with_account("openai", lambda p, k: "r2", "p2")
        self.assertTrue(r1.success)
        self.assertTrue(r2.success)
        self.assertEqual(r1.response, "r1")
        self.assertEqual(r2.response, "r2")

    def test_default_pool_created_when_none(self) -> None:
        mgr = AccountPoolManager()
        self.assertIsInstance(mgr.pool, AccountPool)


if __name__ == "__main__":
    unittest.main()
