from __future__ import annotations

import unittest
from datetime import UTC, datetime

from gracekelly.storage.base import TaskEventRecord, TaskRecord, TaskStepRecord
from gracekelly.storage.memory import InMemoryTaskRepository


class InMemoryRepositoryTests(unittest.TestCase):
    def test_list_recent_orders_tasks_by_accepted_at_desc(self) -> None:
        repository = InMemoryTaskRepository()
        older = datetime(2026, 3, 17, 10, 0, tzinfo=UTC)
        newer = datetime(2026, 3, 17, 10, 5, tzinfo=UTC)
        repository.save_task_with_steps(
            TaskRecord(
                task_id="task-older",
                status="completed",
                accepted_at=older,
                completed_at=older,
                duration_ms=1,
                prompt="older",
                reasoning=False,
                execution_mode="dry-run",
                dry_run=True,
                model_count=1,
                quorum=1,
                merge_strategy="first_success",
                adapter_hint="auto",
                cancel_on_quorum=True,
            ),
            [],
        )
        repository.save_task_with_steps(
            TaskRecord(
                task_id="task-newer",
                status="completed",
                accepted_at=newer,
                completed_at=newer,
                duration_ms=1,
                prompt="newer",
                reasoning=False,
                execution_mode="dry-run",
                dry_run=True,
                model_count=1,
                quorum=1,
                merge_strategy="first_success",
                adapter_hint="auto",
                cancel_on_quorum=True,
            ),
            [],
        )

        tasks = repository.list_recent(1)

        self.assertEqual([task.task_id for task in tasks], ["task-newer"])

    def test_list_recent_can_filter_by_status_and_dry_run(self) -> None:
        repository = InMemoryTaskRepository()
        accepted_at = datetime(2026, 3, 17, 10, 0, tzinfo=UTC)
        repository.save_task_with_steps(
            TaskRecord(
                task_id="task-completed",
                status="completed",
                accepted_at=accepted_at,
                completed_at=accepted_at,
                duration_ms=1,
                prompt="completed",
                reasoning=False,
                execution_mode="dry-run",
                dry_run=True,
                model_count=1,
                quorum=1,
                merge_strategy="first_success",
                adapter_hint="auto",
                cancel_on_quorum=True,
            ),
            [],
        )
        repository.save_task_with_steps(
            TaskRecord(
                task_id="task-failed",
                status="failed",
                accepted_at=accepted_at.replace(minute=1),
                completed_at=accepted_at.replace(minute=1),
                duration_ms=1,
                prompt="failed",
                reasoning=False,
                execution_mode="api",
                dry_run=False,
                model_count=1,
                quorum=1,
                merge_strategy="first_success",
                adapter_hint="auto",
                cancel_on_quorum=True,
                failure_code="provider_unavailable",
            ),
            [],
        )

        tasks = repository.list_recent(
            10,
            status="failed",
            execution_mode="api",
            dry_run=False,
            failure_code="provider_unavailable",
        )

        self.assertEqual([task.task_id for task in tasks], ["task-failed"])

    def test_list_events_orders_by_sequence_number(self) -> None:
        repository = InMemoryTaskRepository()
        created_at = datetime.now(UTC)
        repository.append_event(
            TaskEventRecord(
                event_id="event-2",
                task_id="task-1",
                sequence_no=2,
                event_type="task.completed",
                created_at=created_at,
                payload={},
            )
        )
        repository.append_event(
            TaskEventRecord(
                event_id="event-1",
                task_id="task-1",
                sequence_no=1,
                event_type="task.accepted",
                created_at=created_at,
                payload={},
            )
        )

        events = repository.list_events("task-1")

        self.assertEqual([event.sequence_no for event in events], [1, 2])
        self.assertEqual([event.event_type for event in events], ["task.accepted", "task.completed"])

    def test_append_event_rejects_duplicate_sequence_number_per_task(self) -> None:
        repository = InMemoryTaskRepository()
        created_at = datetime.now(UTC)
        repository.append_event(
            TaskEventRecord(
                event_id="event-1",
                task_id="task-1",
                sequence_no=1,
                event_type="task.accepted",
                created_at=created_at,
                payload={},
            )
        )

        with self.assertRaises(ValueError):
            repository.append_event(
                TaskEventRecord(
                    event_id="event-2",
                    task_id="task-1",
                    sequence_no=1,
                    event_type="task.completed",
                    created_at=created_at,
                    payload={},
                )
            )

    def test_replace_task_snapshot_replaces_steps_and_events_for_task(self) -> None:
        repository = InMemoryTaskRepository()
        created_at = datetime.now(UTC)
        repository.save_task_with_steps(
            TaskRecord(
                task_id="task-1",
                status="completed",
                accepted_at=created_at,
                completed_at=created_at,
                duration_ms=1,
                prompt="before",
                reasoning=False,
                execution_mode="dry-run",
                dry_run=True,
                model_count=1,
                quorum=1,
                merge_strategy="first_success",
                adapter_hint="auto",
                cancel_on_quorum=True,
            ),
            [
                TaskStepRecord(
                    task_id="task-1",
                    step_index=1,
                    model_id="old-model",
                    model_display_name="Old Model",
                    backend="api",
                    provider="old",
                    status="completed",
                )
            ],
        )
        repository.append_event(
            TaskEventRecord(
                event_id="event-1",
                task_id="task-1",
                sequence_no=1,
                event_type="task.accepted",
                created_at=created_at,
                payload={"before": True},
            )
        )

        repository.replace_task_snapshot(
            TaskRecord(
                task_id="task-1",
                status="failed",
                accepted_at=created_at,
                completed_at=created_at,
                duration_ms=2,
                prompt="after",
                reasoning=False,
                execution_mode="api",
                dry_run=False,
                model_count=1,
                quorum=1,
                merge_strategy="first_success",
                adapter_hint="auto",
                cancel_on_quorum=True,
                failure_code="provider_unavailable",
            ),
            [
                TaskStepRecord(
                    task_id="task-1",
                    step_index=1,
                    model_id="new-model",
                    model_display_name="New Model",
                    backend="browser",
                    provider="perplexity",
                    status="failed",
                    failure_code="provider_unavailable",
                )
            ],
            [
                TaskEventRecord(
                    event_id="event-2",
                    task_id="task-1",
                    sequence_no=1,
                    event_type="task.failed",
                    created_at=created_at,
                    payload={"after": True},
                )
            ],
        )

        task = repository.get("task-1")
        steps = repository.list_steps("task-1")
        events = repository.list_events("task-1")

        self.assertEqual(task.prompt, "after")
        self.assertEqual(task.status, "failed")
        self.assertEqual(steps[0].model_id, "new-model")
        self.assertEqual(steps[0].backend, "browser")
        self.assertEqual(len(events), 1)
        self.assertEqual(events[0].event_type, "task.failed")
        self.assertEqual(events[0].payload, {"after": True})


if __name__ == "__main__":
    unittest.main()
