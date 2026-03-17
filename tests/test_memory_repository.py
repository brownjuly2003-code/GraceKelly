from __future__ import annotations

from datetime import datetime, timezone
import unittest

from gracekelly.storage.base import TaskEventRecord
from gracekelly.storage.memory import InMemoryTaskRepository


class InMemoryRepositoryTests(unittest.TestCase):
    def test_list_events_orders_by_sequence_number(self) -> None:
        repository = InMemoryTaskRepository()
        created_at = datetime.now(timezone.utc)
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
        created_at = datetime.now(timezone.utc)
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


if __name__ == "__main__":
    unittest.main()
