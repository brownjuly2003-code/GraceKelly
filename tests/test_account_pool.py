from __future__ import annotations

from datetime import UTC, datetime, timedelta
import unittest

from gracekelly.core.account_pool import Account, AccountPool, AccountPoolConfig


class _Clock:
    def __init__(self, now: datetime) -> None:
        self.now = now

    def __call__(self) -> datetime:
        return self.now


class AccountPoolTests(unittest.TestCase):
    def _account(
        self,
        id: str = "acct-1",
        credential: str = "key-1",
        provider: str = "mistral",
        kind: str = "api_key",
    ) -> Account:
        return Account(id=id, credential=credential, provider=provider, kind=kind)

    def test_acquire_returns_available_account(self) -> None:
        pool = AccountPool([self._account()])
        acct = pool.acquire("mistral")
        self.assertIsNotNone(acct)
        self.assertEqual(acct.id, "acct-1")
        self.assertTrue(acct.busy)

    def test_acquire_returns_none_when_all_busy(self) -> None:
        pool = AccountPool([self._account()])
        pool.acquire("mistral")
        self.assertIsNone(pool.acquire("mistral"))

    def test_release_makes_account_available_again(self) -> None:
        pool = AccountPool([self._account()])
        pool.acquire("mistral")
        pool.release("acct-1")
        acct = pool.acquire("mistral")
        self.assertIsNotNone(acct)
        self.assertEqual(acct.total_uses, 2)

    def test_acquire_filters_by_provider(self) -> None:
        pool = AccountPool([
            self._account(id="a1", provider="mistral"),
            self._account(id="a2", provider="openai"),
        ])
        acct = pool.acquire("openai")
        self.assertEqual(acct.id, "a2")

    def test_acquire_filters_by_kind(self) -> None:
        pool = AccountPool([
            self._account(id="a1", kind="api_key"),
            self._account(id="a2", kind="browser_profile"),
        ])
        acct = pool.acquire("mistral", kind="browser_profile")
        self.assertEqual(acct.id, "a2")

    def test_acquire_prefers_least_recently_used(self) -> None:
        clock = _Clock(datetime(2026, 3, 19, 12, 0, tzinfo=UTC))
        pool = AccountPool(
            [
                self._account(id="a1"),
                self._account(id="a2"),
            ],
            now_factory=clock,
        )
        first = pool.acquire("mistral")
        pool.release(first.id)
        clock.now += timedelta(seconds=1)
        second = pool.acquire("mistral")
        self.assertEqual(second.id, "a2")

    def test_cooldown_blocks_acquisition(self) -> None:
        clock = _Clock(datetime(2026, 3, 19, 12, 0, tzinfo=UTC))
        pool = AccountPool(
            [self._account()],
            config=AccountPoolConfig(default_cooldown_seconds=60),
            now_factory=clock,
        )
        pool.acquire("mistral")
        pool.mark_cooldown("acct-1")
        self.assertIsNone(pool.acquire("mistral"))

    def test_cooldown_expires(self) -> None:
        clock = _Clock(datetime(2026, 3, 19, 12, 0, tzinfo=UTC))
        pool = AccountPool(
            [self._account()],
            config=AccountPoolConfig(default_cooldown_seconds=60),
            now_factory=clock,
        )
        pool.acquire("mistral")
        pool.mark_cooldown("acct-1")
        clock.now += timedelta(seconds=61)
        acct = pool.acquire("mistral")
        self.assertIsNotNone(acct)

    def test_custom_cooldown_duration(self) -> None:
        clock = _Clock(datetime(2026, 3, 19, 12, 0, tzinfo=UTC))
        pool = AccountPool([self._account()], now_factory=clock)
        pool.acquire("mistral")
        pool.mark_cooldown("acct-1", seconds=10)
        clock.now += timedelta(seconds=11)
        self.assertIsNotNone(pool.acquire("mistral"))

    def test_available_count(self) -> None:
        pool = AccountPool([
            self._account(id="a1"),
            self._account(id="a2"),
            self._account(id="a3", provider="openai"),
        ])
        self.assertEqual(pool.available_count("mistral"), 2)
        pool.acquire("mistral")
        self.assertEqual(pool.available_count("mistral"), 1)
        self.assertEqual(pool.available_count("openai"), 1)

    def test_available_count_with_kind(self) -> None:
        pool = AccountPool([
            self._account(id="a1", kind="api_key"),
            self._account(id="a2", kind="browser_profile"),
        ])
        self.assertEqual(pool.available_count("mistral", kind="api_key"), 1)

    def test_snapshot(self) -> None:
        pool = AccountPool([
            self._account(id="a1"),
            self._account(id="a2"),
        ])
        pool.acquire("mistral")
        snap = pool.snapshot()
        self.assertEqual(len(snap), 2)
        statuses = {s["id"]: s["status"] for s in snap}
        self.assertEqual(statuses["a1"], "busy")
        self.assertEqual(statuses["a2"], "available")

    def test_snapshot_shows_cooldown(self) -> None:
        clock = _Clock(datetime(2026, 3, 19, 12, 0, tzinfo=UTC))
        pool = AccountPool([self._account()], now_factory=clock)
        pool.acquire("mistral")
        pool.mark_cooldown("acct-1")
        snap = pool.snapshot()
        self.assertEqual(snap[0]["status"], "cooldown")
        self.assertEqual(snap[0]["total_failures"], 1)

    def test_add_account(self) -> None:
        pool = AccountPool()
        pool.add(self._account())
        self.assertEqual(pool.available_count("mistral"), 1)

    def test_add_duplicate_raises(self) -> None:
        pool = AccountPool([self._account()])
        with self.assertRaises(ValueError):
            pool.add(self._account())

    def test_empty_pool_returns_none(self) -> None:
        pool = AccountPool()
        self.assertIsNone(pool.acquire("mistral"))

    def test_mark_cooldown_increments_failures(self) -> None:
        pool = AccountPool([self._account()])
        pool.acquire("mistral")
        pool.mark_cooldown("acct-1")
        pool.mark_cooldown("acct-1")
        snap = pool.snapshot()
        self.assertEqual(snap[0]["total_failures"], 2)

    def test_mark_cooldown_unknown_account_is_noop(self) -> None:
        pool = AccountPool()
        pool.mark_cooldown("unknown")

    def test_release_unknown_account_is_noop(self) -> None:
        pool = AccountPool()
        pool.release("unknown")


if __name__ == "__main__":
    unittest.main()
