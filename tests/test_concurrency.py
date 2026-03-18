from __future__ import annotations

import threading
import unittest

from gracekelly.core.concurrency import ModelConcurrencyGate


class ModelConcurrencyGateTests(unittest.TestCase):
    def setUp(self) -> None:
        self.gate = ModelConcurrencyGate()

    def test_acquire_within_limit(self) -> None:
        self.assertTrue(self.gate.try_acquire("m1", limit=2))
        self.assertTrue(self.gate.try_acquire("m1", limit=2))

    def test_acquire_at_limit_returns_false(self) -> None:
        self.gate.try_acquire("m1", limit=1)
        self.assertFalse(self.gate.try_acquire("m1", limit=1))

    def test_release_frees_slot(self) -> None:
        self.gate.try_acquire("m1", limit=1)
        self.gate.release("m1")
        self.assertTrue(self.gate.try_acquire("m1", limit=1))

    def test_release_without_acquire_raises(self) -> None:
        with self.assertRaises(RuntimeError):
            self.gate.release("m1")

    def test_release_decrements_correctly(self) -> None:
        self.gate.try_acquire("m1", limit=3)
        self.gate.try_acquire("m1", limit=3)
        self.gate.release("m1")
        self.assertEqual(self.gate.snapshot(), {"m1": 1})

    def test_release_last_slot_removes_key(self) -> None:
        self.gate.try_acquire("m1", limit=1)
        self.gate.release("m1")
        self.assertEqual(self.gate.snapshot(), {})

    def test_limit_below_one_raises(self) -> None:
        with self.assertRaises(ValueError):
            self.gate.try_acquire("m1", limit=0)

    def test_independent_models(self) -> None:
        self.gate.try_acquire("m1", limit=1)
        self.assertTrue(self.gate.try_acquire("m2", limit=1))
        self.assertEqual(self.gate.snapshot(), {"m1": 1, "m2": 1})

    def test_snapshot_returns_copy(self) -> None:
        self.gate.try_acquire("m1", limit=2)
        snap = self.gate.snapshot()
        snap["m1"] = 999
        self.assertEqual(self.gate.snapshot(), {"m1": 1})

    def test_concurrent_acquire_release(self) -> None:
        results: list[bool] = []
        errors: list[Exception] = []

        def worker() -> None:
            try:
                acquired = self.gate.try_acquire("m1", limit=2)
                results.append(acquired)
                if acquired:
                    threading.Event().wait(0.01)
                    self.gate.release("m1")
            except Exception as exc:
                errors.append(exc)

        threads = [threading.Thread(target=worker) for _ in range(20)]
        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=5)

        self.assertEqual(errors, [])
        self.assertEqual(self.gate.snapshot(), {})

    def test_concurrent_stress_no_negative_counts(self) -> None:
        barrier = threading.Barrier(10)
        errors: list[Exception] = []

        def acquire_release_cycle() -> None:
            try:
                barrier.wait(timeout=5)
                for _ in range(50):
                    if self.gate.try_acquire("m1", limit=3):
                        self.gate.release("m1")
            except Exception as exc:
                errors.append(exc)

        threads = [threading.Thread(target=acquire_release_cycle) for _ in range(10)]
        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=10)

        self.assertEqual(errors, [])
        self.assertEqual(self.gate.snapshot(), {})
