from __future__ import annotations

import unittest
from unittest.mock import MagicMock

from gracekelly.core.orchestrator import OrchestratorService
from gracekelly.storage.base import TaskEventRecord


def _make_event(task_id: str = "t1", seq: int = 1) -> TaskEventRecord:
    from datetime import UTC, datetime

    from gracekelly.core.contracts import EventType

    return TaskEventRecord(
        event_id=f"ev-{seq}",
        task_id=task_id,
        sequence_no=seq,
        event_type=EventType.TASK_ACCEPTED,
        created_at=datetime.now(UTC),
        payload={},
    )


class EventBufferTests(unittest.TestCase):
    def _make_service(self) -> OrchestratorService:
        repo = MagicMock()
        router = MagicMock()
        return OrchestratorService(repo, router)

    def test_event_buffered_when_append_fails(self) -> None:
        svc = self._make_service()
        svc._repository.append_event.side_effect = RuntimeError("db down")
        event = _make_event()
        svc._append_event_safe(event)
        self.assertEqual(len(svc._event_buffer), 1)
        self.assertIs(svc._event_buffer[0], event)

    def test_buffer_flushed_on_next_call(self) -> None:
        svc = self._make_service()
        event = _make_event()
        svc._event_buffer.append(event)
        svc._repository.append_event.return_value = None
        svc._flush_buffer()
        self.assertEqual(len(svc._event_buffer), 0)
        svc._repository.append_event.assert_called_once_with(event)

    def test_buffer_stops_flushing_on_failure(self) -> None:
        svc = self._make_service()
        ev1 = _make_event(seq=1)
        ev2 = _make_event(seq=2)
        svc._event_buffer.append(ev1)
        svc._event_buffer.append(ev2)
        svc._repository.append_event.side_effect = RuntimeError("still down")
        svc._flush_buffer()
        self.assertEqual(len(svc._event_buffer), 2)

    def test_buffer_maxlen_enforced(self) -> None:
        svc = self._make_service()
        self.assertEqual(svc._event_buffer.maxlen, 500)
        for i in range(600):
            svc._event_buffer.append(_make_event(seq=i))
        self.assertEqual(len(svc._event_buffer), 500)


if __name__ == "__main__":
    unittest.main()
