from __future__ import annotations

import unittest
from datetime import UTC, datetime
from unittest.mock import MagicMock

try:
    from fastapi.testclient import TestClient
except ModuleNotFoundError:  # pragma: no cover
    TestClient = None  # type: ignore[assignment,misc]

from gracekelly.core.contracts import (
    AdapterHint,
    EventType,
    ExecutionMode,
    MergeStrategy,
    TaskStatus,
)
from gracekelly.storage.base import TaskEventRecord, TaskRecord
from gracekelly.storage.memory import InMemoryTaskRepository

if TestClient is not None:
    from gracekelly.config import Settings
    from gracekelly.core.orchestrator import OrchestratorService
    from gracekelly.main import create_app

_NOW = datetime(2026, 3, 28, 12, 0, tzinfo=UTC)
_TASK_UUID = "12345678-1234-1234-1234-123456789abc"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _task(task_id: str = "t1") -> TaskRecord:
    return TaskRecord(
        task_id=task_id,
        status=TaskStatus.COMPLETED,
        accepted_at=_NOW,
        completed_at=_NOW,
        duration_ms=100,
        prompt="test",
        reasoning=False,
        execution_mode=ExecutionMode.API,
        dry_run=False,
        model_count=1,
        quorum=1,
        merge_strategy=MergeStrategy.FIRST_SUCCESS,
        adapter_hint=AdapterHint.API,
        cancel_on_quorum=False,
    )


def _event(task_id: str, seq: int) -> TaskEventRecord:
    return TaskEventRecord(
        event_id=f"e-{task_id}-{seq}",
        task_id=task_id,
        sequence_no=seq,
        event_type=EventType.TASK_ACCEPTED,
        created_at=_NOW,
    )


def _make_repo_with_events(n: int, task_id: str = "t1") -> InMemoryTaskRepository:
    repo = InMemoryTaskRepository()
    repo.save_task_with_steps(_task(task_id), [])
    for i in range(1, n + 1):
        repo.append_event(_event(task_id, i))
    return repo


def _make_repo_with_events_uuid(n: int) -> InMemoryTaskRepository:
    return _make_repo_with_events(n, task_id=_TASK_UUID)


# ---------------------------------------------------------------------------
# Storage-level pagination tests
# ---------------------------------------------------------------------------


class EventPaginationStorageTests(unittest.TestCase):
    def test_no_limit_returns_all_events(self) -> None:
        repo = _make_repo_with_events(10)
        page, total = repo.list_events_paginated("t1")
        self.assertEqual(total, 10)
        self.assertEqual(len(page), 10)

    def test_with_limit_returns_correct_slice(self) -> None:
        repo = _make_repo_with_events(10)
        page, total = repo.list_events_paginated("t1", limit=3)
        self.assertEqual(total, 10)
        self.assertEqual(len(page), 3)
        self.assertEqual([e.sequence_no for e in page], [1, 2, 3])

    def test_with_offset_skips_first_events(self) -> None:
        repo = _make_repo_with_events(10)
        page, total = repo.list_events_paginated("t1", offset=5)
        self.assertEqual(total, 10)
        self.assertEqual(len(page), 5)
        self.assertEqual(page[0].sequence_no, 6)

    def test_limit_and_offset_combined(self) -> None:
        repo = _make_repo_with_events(10)
        page, total = repo.list_events_paginated("t1", limit=3, offset=4)
        self.assertEqual(total, 10)
        self.assertEqual(len(page), 3)
        self.assertEqual([e.sequence_no for e in page], [5, 6, 7])

    def test_returns_total_count(self) -> None:
        repo = _make_repo_with_events(7)
        _, total = repo.list_events_paginated("t1", limit=2)
        self.assertEqual(total, 7)

    def test_empty_task_returns_empty_and_zero(self) -> None:
        repo = InMemoryTaskRepository()
        repo.save_task_with_steps(_task(), [])
        page, total = repo.list_events_paginated("t1")
        self.assertEqual(total, 0)
        self.assertEqual(page, [])

    def test_offset_beyond_end_returns_empty_page(self) -> None:
        repo = _make_repo_with_events(5)
        page, total = repo.list_events_paginated("t1", limit=10, offset=100)
        self.assertEqual(total, 5)
        self.assertEqual(page, [])

    def test_events_ordered_by_sequence_no(self) -> None:
        repo = InMemoryTaskRepository()
        repo.save_task_with_steps(_task(), [])
        # append out of order (internal dict order vs sequence_no)
        for seq in [3, 1, 2]:
            repo.append_event(_event("t1", seq))
        page, _ = repo.list_events_paginated("t1")
        self.assertEqual([e.sequence_no for e in page], [1, 2, 3])

    def test_unknown_task_returns_empty(self) -> None:
        repo = InMemoryTaskRepository()
        page, total = repo.list_events_paginated("unknown")
        self.assertEqual(total, 0)
        self.assertEqual(page, [])

    def test_zero_offset_same_as_default(self) -> None:
        repo = _make_repo_with_events(5)
        page_default, total_default = repo.list_events_paginated("t1", limit=3)
        page_zero, total_zero = repo.list_events_paginated("t1", limit=3, offset=0)
        self.assertEqual(total_default, total_zero)
        self.assertEqual([e.event_id for e in page_default], [e.event_id for e in page_zero])

    def test_limit_larger_than_available_returns_remainder(self) -> None:
        repo = _make_repo_with_events(4)
        page, total = repo.list_events_paginated("t1", limit=100)
        self.assertEqual(total, 4)
        self.assertEqual(len(page), 4)

    def test_multiple_tasks_isolated(self) -> None:
        repo = InMemoryTaskRepository()
        for tid in ("task-a", "task-b"):
            repo.save_task_with_steps(_task(tid), [])
        for i in range(1, 6):
            repo.append_event(_event("task-a", i))
        for i in range(1, 3):
            repo.append_event(_event("task-b", i))

        _, total_a = repo.list_events_paginated("task-a")
        _, total_b = repo.list_events_paginated("task-b")

        self.assertEqual(total_a, 5)
        self.assertEqual(total_b, 2)


# ---------------------------------------------------------------------------
# OrchestratorService delegation tests
# ---------------------------------------------------------------------------


class OrchestratorEventPaginationTests(unittest.TestCase):
    def _make_service(self, n: int = 5) -> tuple[OrchestratorService, str]:
        if TestClient is None:  # pragma: no cover
            self.skipTest("fastapi not installed")
        repo = _make_repo_with_events(n)
        execution_router = MagicMock()
        service = OrchestratorService(repo, execution_router)
        return service, "t1"

    def test_service_returns_paginated_events(self) -> None:
        service, task_id = self._make_service(10)
        page, total = service.list_task_events_paginated(task_id, limit=4)
        self.assertEqual(total, 10)
        self.assertEqual(len(page), 4)

    def test_service_no_limit_returns_all(self) -> None:
        service, task_id = self._make_service(8)
        page, total = service.list_task_events_paginated(task_id)
        self.assertEqual(total, 8)
        self.assertEqual(len(page), 8)

    def test_service_offset(self) -> None:
        service, task_id = self._make_service(10)
        page, total = service.list_task_events_paginated(task_id, limit=3, offset=7)
        self.assertEqual(total, 10)
        self.assertEqual(len(page), 3)
        self.assertEqual(page[0].sequence_no, 8)


# ---------------------------------------------------------------------------
# HTTP API route tests
# ---------------------------------------------------------------------------


@unittest.skipIf(TestClient is None, "fastapi.testclient is not installed")
class EventPaginationRouteTests(unittest.TestCase):
    def _build_client(self, n_events: int = 10) -> tuple[TestClient, str]:
        app = create_app(
            Settings(
                env="test",
                host="127.0.0.1",
                port=8011,
                log_level="INFO",
                storage_backend="memory",
                postgres_dsn=None,
                mistral_api_key=None,
                mistral_base_url="https://api.mistral.ai/v1",
                mistral_timeout_seconds=1.0,
                openai_api_key=None,
                openai_base_url="https://api.openai.com/v1",
                openai_timeout_seconds=1.0,
                browser_enabled=False,
                browser_profile_dir=None,
                browser_base_url="https://www.perplexity.ai",
            )
        )
        repo = _make_repo_with_events_uuid(n_events)
        app.state.task_repository = repo
        app.state.orchestrator_service = OrchestratorService(
            repo,
            execution_router=app.state.execution_router,
        )
        return TestClient(app), _TASK_UUID

    def test_get_task_without_pagination_returns_all_events(self) -> None:
        client, task_id = self._build_client(5)
        resp = client.get(f"/api/v1/tasks/{task_id}")
        self.assertEqual(resp.status_code, 200)
        body = resp.json()
        self.assertEqual(len(body["events"]), 5)
        self.assertEqual(body["events_total"], 5)

    def test_get_task_with_limit(self) -> None:
        client, task_id = self._build_client(10)
        resp = client.get(f"/api/v1/tasks/{task_id}?events_limit=3")
        self.assertEqual(resp.status_code, 200)
        body = resp.json()
        self.assertEqual(len(body["events"]), 3)
        self.assertEqual(body["events_total"], 10)

    def test_get_task_with_offset(self) -> None:
        client, task_id = self._build_client(10)
        resp = client.get(f"/api/v1/tasks/{task_id}?events_offset=7")
        self.assertEqual(resp.status_code, 200)
        body = resp.json()
        self.assertEqual(len(body["events"]), 3)
        self.assertEqual(body["events_total"], 10)

    def test_get_task_limit_and_offset(self) -> None:
        client, task_id = self._build_client(10)
        resp = client.get(f"/api/v1/tasks/{task_id}?events_limit=2&events_offset=5")
        self.assertEqual(resp.status_code, 200)
        body = resp.json()
        self.assertEqual(len(body["events"]), 2)
        self.assertEqual(body["events_total"], 10)

    def test_get_task_events_total_field_present(self) -> None:
        client, task_id = self._build_client(3)
        resp = client.get(f"/api/v1/tasks/{task_id}")
        self.assertEqual(resp.status_code, 200)
        self.assertIn("events_total", resp.json())

    def test_get_task_limit_zero_rejected(self) -> None:
        client, task_id = self._build_client(5)
        resp = client.get(f"/api/v1/tasks/{task_id}?events_limit=0")
        self.assertEqual(resp.status_code, 422)

    def test_get_task_limit_above_1000_rejected(self) -> None:
        client, task_id = self._build_client(5)
        resp = client.get(f"/api/v1/tasks/{task_id}?events_limit=1001")
        self.assertEqual(resp.status_code, 422)

    def test_get_task_negative_offset_rejected(self) -> None:
        client, task_id = self._build_client(5)
        resp = client.get(f"/api/v1/tasks/{task_id}?events_offset=-1")
        self.assertEqual(resp.status_code, 422)

    def test_get_task_offset_beyond_end_returns_empty_events(self) -> None:
        client, task_id = self._build_client(5)
        resp = client.get(f"/api/v1/tasks/{task_id}?events_offset=999")
        self.assertEqual(resp.status_code, 200)
        body = resp.json()
        self.assertEqual(len(body["events"]), 0)
        self.assertEqual(body["events_total"], 5)

    def test_get_task_limit_1000_accepted(self) -> None:
        client, task_id = self._build_client(5)
        resp = client.get(f"/api/v1/tasks/{task_id}?events_limit=1000")
        self.assertEqual(resp.status_code, 200)

    def test_get_task_offset_zero_same_as_default(self) -> None:
        client, task_id = self._build_client(5)
        resp_default = client.get(f"/api/v1/tasks/{task_id}?events_limit=3")
        resp_zero = client.get(f"/api/v1/tasks/{task_id}?events_limit=3&events_offset=0")
        self.assertEqual(resp_default.json()["events"], resp_zero.json()["events"])


if __name__ == "__main__":
    unittest.main()
