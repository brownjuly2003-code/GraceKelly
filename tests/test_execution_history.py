from __future__ import annotations

import unittest

from gracekelly.core.execution_history import ExecutionHistory
from gracekelly.core.task_classifier import TaskType


class TestExecutionHistory(unittest.TestCase):
    def setUp(self) -> None:
        self.history = ExecutionHistory()

    def test_record_and_retrieve(self) -> None:
        self.history.record("gpt-5", TaskType.CODING, "completed", 100)
        records = self.history.list_recent()
        self.assertEqual(len(records), 1)
        self.assertEqual(records[0].model_id, "gpt-5")
        self.assertEqual(records[0].task_type, TaskType.CODING)
        self.assertEqual(records[0].status, "completed")
        self.assertEqual(records[0].duration_ms, 100)

    def test_list_recent_respects_limit(self) -> None:
        for i in range(10):
            self.history.record("m", TaskType.GENERAL, "completed", i)
        result = self.history.list_recent(limit=3)
        self.assertEqual(len(result), 3)

    def test_list_recent_newest_first(self) -> None:
        self.history.record("m", TaskType.GENERAL, "completed", 10)
        self.history.record("m", TaskType.GENERAL, "completed", 20)
        self.history.record("m", TaskType.GENERAL, "completed", 30)
        result = self.history.list_recent()
        self.assertEqual(result[0].duration_ms, 30)
        self.assertEqual(result[2].duration_ms, 10)

    def test_list_by_model(self) -> None:
        self.history.record("gpt-5", TaskType.CODING, "completed", 100)
        self.history.record("claude", TaskType.CODING, "completed", 200)
        self.history.record("gpt-5", TaskType.MATH, "failed", 300)
        result = self.history.list_by_model("gpt-5")
        self.assertEqual(len(result), 2)
        self.assertTrue(all(r.model_id == "gpt-5" for r in result))

    def test_list_by_task_type(self) -> None:
        self.history.record("m", TaskType.CODING, "completed", 100)
        self.history.record("m", TaskType.MATH, "completed", 200)
        self.history.record("m", TaskType.CODING, "failed", 300)
        result = self.history.list_by_task_type(TaskType.CODING)
        self.assertEqual(len(result), 2)
        self.assertTrue(all(r.task_type == TaskType.CODING for r in result))

    def test_success_rate_all_completed(self) -> None:
        for _ in range(5):
            self.history.record("m", TaskType.GENERAL, "completed", 100)
        self.assertAlmostEqual(self.history.success_rate(), 1.0)

    def test_success_rate_none_completed(self) -> None:
        for _ in range(5):
            self.history.record("m", TaskType.GENERAL, "failed", 100)
        self.assertAlmostEqual(self.history.success_rate(), 0.0)

    def test_success_rate_mixed(self) -> None:
        self.history.record("m", TaskType.GENERAL, "completed", 100)
        self.history.record("m", TaskType.GENERAL, "failed", 100)
        self.history.record("m", TaskType.GENERAL, "completed", 100)
        self.history.record("m", TaskType.GENERAL, "failed", 100)
        self.assertAlmostEqual(self.history.success_rate(), 0.5)

    def test_success_rate_with_model_filter(self) -> None:
        self.history.record("gpt-5", TaskType.GENERAL, "completed", 100)
        self.history.record("gpt-5", TaskType.GENERAL, "completed", 100)
        self.history.record("claude", TaskType.GENERAL, "failed", 100)
        self.assertAlmostEqual(self.history.success_rate("gpt-5"), 1.0)
        self.assertAlmostEqual(self.history.success_rate("claude"), 0.0)

    def test_avg_duration_ms(self) -> None:
        self.history.record("m", TaskType.GENERAL, "completed", 100)
        self.history.record("m", TaskType.GENERAL, "completed", 200)
        self.history.record("m", TaskType.GENERAL, "completed", 300)
        self.assertAlmostEqual(self.history.avg_duration_ms(), 200.0)

    def test_avg_duration_ms_with_model_filter(self) -> None:
        self.history.record("gpt-5", TaskType.GENERAL, "completed", 100)
        self.history.record("gpt-5", TaskType.GENERAL, "completed", 300)
        self.history.record("claude", TaskType.GENERAL, "completed", 1000)
        self.assertAlmostEqual(self.history.avg_duration_ms("gpt-5"), 200.0)

    def test_count(self) -> None:
        self.assertEqual(self.history.count(), 0)
        self.history.record("m", TaskType.GENERAL, "completed", 100)
        self.history.record("m", TaskType.GENERAL, "failed", 200)
        self.assertEqual(self.history.count(), 2)

    def test_clear(self) -> None:
        self.history.record("m", TaskType.GENERAL, "completed", 100)
        self.history.clear()
        self.assertEqual(self.history.count(), 0)
        self.assertEqual(self.history.list_recent(), [])

    def test_empty_history(self) -> None:
        self.assertAlmostEqual(self.history.success_rate(), 0.0)
        self.assertAlmostEqual(self.history.avg_duration_ms(), 0.0)
        self.assertEqual(self.history.count(), 0)
        self.assertEqual(self.history.list_recent(), [])

    def test_record_is_frozen(self) -> None:
        self.history.record("m", TaskType.GENERAL, "completed", 100)
        rec = self.history.list_recent()[0]
        with self.assertRaises(AttributeError):
            setattr(rec, "model_id", "other")


class TestExecutionHistoryEdgeCases(unittest.TestCase):
    def setUp(self) -> None:
        self.history = ExecutionHistory()

    def test_list_by_model_unknown_model_returns_empty(self) -> None:
        self.history.record("gpt-5", TaskType.CODING, "completed", 100)
        result = self.history.list_by_model("unknown-model")
        self.assertEqual(result, [])

    def test_list_by_model_respects_limit(self) -> None:
        for i in range(10):
            self.history.record("m1", TaskType.GENERAL, "completed", i * 10)
        result = self.history.list_by_model("m1", limit=3)
        self.assertEqual(len(result), 3)

    def test_list_by_model_newest_first(self) -> None:
        for dur in (10, 20, 30):
            self.history.record("m1", TaskType.GENERAL, "completed", dur)
        result = self.history.list_by_model("m1")
        self.assertEqual(result[0].duration_ms, 30)

    def test_list_by_task_type_unknown_type_returns_empty(self) -> None:
        self.history.record("m1", TaskType.CODING, "completed", 100)
        result = self.history.list_by_task_type(TaskType.MATH)
        self.assertEqual(result, [])

    def test_list_by_task_type_respects_limit(self) -> None:
        for i in range(8):
            self.history.record("m", TaskType.CODING, "completed", i * 10)
        result = self.history.list_by_task_type(TaskType.CODING, limit=2)
        self.assertEqual(len(result), 2)

    def test_list_by_task_type_newest_first(self) -> None:
        for dur in (5, 15, 25):
            self.history.record("m", TaskType.RESEARCH, "completed", dur)
        result = self.history.list_by_task_type(TaskType.RESEARCH)
        self.assertEqual(result[0].duration_ms, 25)

    def test_success_rate_unknown_model_returns_zero(self) -> None:
        self.history.record("m1", TaskType.GENERAL, "completed", 100)
        self.assertAlmostEqual(self.history.success_rate("nonexistent"), 0.0)

    def test_avg_duration_ms_unknown_model_returns_zero(self) -> None:
        self.history.record("m1", TaskType.GENERAL, "completed", 100)
        self.assertAlmostEqual(self.history.avg_duration_ms("nonexistent"), 0.0)

    def test_clear_then_reuse(self) -> None:
        self.history.record("m1", TaskType.GENERAL, "completed", 50)
        self.history.clear()
        self.history.record("m2", TaskType.CODING, "failed", 75)
        self.assertEqual(self.history.count(), 1)
        self.assertEqual(self.history.list_recent()[0].model_id, "m2")

    def test_thread_safety_concurrent_records(self) -> None:
        import threading

        errors: list[Exception] = []

        def add_records() -> None:
            try:
                for i in range(50):
                    self.history.record("m", TaskType.GENERAL, "completed", i)
            except Exception as exc:  # noqa: BLE001
                errors.append(exc)

        threads = [threading.Thread(target=add_records) for _ in range(4)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        self.assertEqual(errors, [])
        self.assertEqual(self.history.count(), 200)

    def test_list_recent_with_limit_greater_than_count(self) -> None:
        self.history.record("m", TaskType.GENERAL, "completed", 1)
        self.history.record("m", TaskType.GENERAL, "completed", 2)
        result = self.history.list_recent(limit=100)
        self.assertEqual(len(result), 2)

    def test_record_timestamp_is_positive(self) -> None:
        self.history.record("m", TaskType.GENERAL, "completed", 100)
        rec = self.history.list_recent()[0]
        self.assertGreater(rec.timestamp, 0.0)


if __name__ == "__main__":
    unittest.main()
