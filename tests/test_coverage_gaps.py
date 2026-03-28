from __future__ import annotations

import unittest
from datetime import UTC, datetime
from unittest.mock import MagicMock, patch

import httpx
from fastapi import FastAPI
from fastapi.testclient import TestClient

from gracekelly.adapters.api.base import BaseApiAdapter
from gracekelly.api.routes.pipeline import router as pipeline_router
from gracekelly.api.routes.smart_v2 import router as smart_v2_router
from gracekelly.core.contracts import (
    EventType,
    ExecutionMode,
    FailureCode,
    StepStatus,
    TaskStatus,
)
from gracekelly.core.pattern_resolver import resolve_from_level
from gracekelly.core.reliability import ReliabilityLevel
from gracekelly.storage.base import TaskEventRecord, TaskRecord, TaskRepository, TaskStepRecord


def _smart_v2_app(*, has_embeddings: bool = True) -> FastAPI:
    app = FastAPI()
    app.include_router(smart_v2_router)

    adapter = MagicMock()
    adapter.execute.return_value = MagicMock(
        status=StepStatus.COMPLETED,
        output_text="Test response. Confidence: 8/10",
        failure_code=None,
        failure_message=None,
    )
    app.state.api_adapters = {"mistral": adapter}
    app.state.embeddings_client = MagicMock() if has_embeddings else None
    return app


def _pipeline_app() -> FastAPI:
    app = FastAPI()
    app.include_router(pipeline_router)

    adapter = MagicMock()
    adapter.has_api_key = True
    adapter.execute.return_value = MagicMock(
        status=StepStatus.COMPLETED,
        output_text="Fallback answer",
        failure_code=None,
        failure_message=None,
    )
    app.state.api_adapters = {"mistral": adapter}
    return app


def _adapter(*, api_key: str | None = "test-key", max_retries: int = 0) -> BaseApiAdapter:
    return BaseApiAdapter(
        api_key=api_key,
        base_url="https://api.example.com",
        timeout_seconds=10.0,
        provider_label="TestProvider",
        max_retries=max_retries,
        retry_backoff_seconds=0.0,
    )


def _make_request() -> MagicMock:
    req = MagicMock()
    req.task_id = "t1"
    req.prompt = "Hello"
    req.reasoning = False
    req.step.model.id = "m1"
    req.step.model.display_name = "M1"
    req.step.model.timeout_seconds = 10
    req.step.provider_model_id = "m1"
    return req


def _mock_httpx_response(content: dict[str, object]) -> MagicMock:
    mock = MagicMock(spec=httpx.Response)
    mock.status_code = 200
    mock.json.return_value = content
    mock.raise_for_status.return_value = None
    return mock


class _StatusValue:
    def __init__(self, value: str) -> None:
        self.value = value


class _BaseRepo(TaskRepository):
    backend_name = "stub"

    def __init__(self) -> None:
        self._events: dict[str, list[TaskEventRecord]] = {}

    def save_task_with_steps(self, task: TaskRecord, steps: list[TaskStepRecord]) -> None:
        raise NotImplementedError

    def get(self, task_id: str) -> TaskRecord | None:
        raise NotImplementedError

    def list_recent(
        self,
        limit: int,
        *,
        status: TaskStatus | None = None,
        execution_mode: ExecutionMode | None = None,
        dry_run: bool | None = None,
        failure_code: FailureCode | None = None,
        before: datetime | None = None,
    ) -> list[TaskRecord]:
        raise NotImplementedError

    def list_steps(self, task_id: str) -> list[TaskStepRecord]:
        raise NotImplementedError

    def append_event(self, event: TaskEventRecord) -> None:
        self._events.setdefault(event.task_id, []).append(event)

    def list_events(self, task_id: str) -> list[TaskEventRecord]:
        return self._events.get(task_id, [])

    def replace_task_snapshot(
        self,
        task: TaskRecord,
        steps: list[TaskStepRecord],
        events: list[TaskEventRecord],
    ) -> None:
        raise NotImplementedError


class SmartV2CoverageGapTests(unittest.TestCase):
    def test_unknown_pattern_returns_400(self) -> None:
        client = TestClient(_smart_v2_app())
        response = client.post("/api/v1/smart/v2", json={"prompt": "Hello", "pattern": "bogus"})
        self.assertEqual(400, response.status_code)
        self.assertIn("Unknown pattern", response.json()["detail"])

    def test_unknown_reliability_level_returns_400(self) -> None:
        client = TestClient(_smart_v2_app())
        response = client.post("/api/v1/smart/v2", json={"prompt": "Hello", "reliability_level": "bogus"})
        self.assertEqual(400, response.status_code)
        self.assertIn("Unknown level", response.json()["detail"])

    def test_decomposition_complexity_uses_high_level(self) -> None:
        from gracekelly.api.routes import smart_v2 as smart_v2_module

        client = TestClient(_smart_v2_app())
        complexity = MagicMock()
        complexity.should_decompose = True
        complexity.level.value = "simple"

        with patch.object(smart_v2_module, "assess_complexity", return_value=complexity), patch.object(
            smart_v2_module, "resolve_from_level", wraps=resolve_from_level
        ) as resolve_mock:
            response = client.post("/api/v1/smart/v2", json={"prompt": "Hello"})

        self.assertEqual(200, response.status_code)
        self.assertEqual(resolve_mock.call_args.args[0], ReliabilityLevel.HIGH)

    def test_complex_non_decomposed_prompt_uses_standard_level(self) -> None:
        from gracekelly.api.routes import smart_v2 as smart_v2_module

        client = TestClient(_smart_v2_app())
        complexity = MagicMock()
        complexity.should_decompose = False
        complexity.level.value = "complex"

        with patch.object(smart_v2_module, "assess_complexity", return_value=complexity), patch.object(
            smart_v2_module, "resolve_from_level", wraps=resolve_from_level
        ) as resolve_mock:
            response = client.post("/api/v1/smart/v2", json={"prompt": "Hello"})

        self.assertEqual(200, response.status_code)
        self.assertEqual(resolve_mock.call_args.args[0], ReliabilityLevel.STANDARD)

    def test_consensus_branch_truncates_dissenting_view(self) -> None:
        from gracekelly.api.routes import smart_v2 as smart_v2_module

        client = TestClient(_smart_v2_app(has_embeddings=True))
        resolved = MagicMock()
        resolved.reasoning = False
        resolved.use_decomposition = False
        resolved.use_consensus = True
        resolved.roles = ()
        resolved.pattern.value = "consensus"
        resolved.reliability_level.value = "standard"
        fake_result = MagicMock()
        fake_result.best_response = "Consensus answer"
        fake_result.weighted_score = 0.88
        fake_result.consensus_result.consensus_score = 0.77
        fake_result.final_result.status = _StatusValue("consensus")
        fake_result.final_result.dissenting_views = [
            MagicMock(perspective="x" * 600, support_ratio=0.25)
        ]

        with patch.object(smart_v2_module, "resolve_from_level", return_value=resolved), patch.object(
            smart_v2_module.ConsensusExecutorV2, "execute", return_value=fake_result
        ):
            response = client.post(
                "/api/v1/smart/v2",
                json={"prompt": "Hello", "reliability_level": "standard"},
            )

        self.assertEqual(200, response.status_code)
        body = response.json()
        self.assertEqual(body["consensus_status"], "consensus")
        self.assertEqual(len(body["dissenting_views"][0]["perspective"]), 500)


class BaseApiAdapterCoverageGapTests(unittest.TestCase):
    def test_os_error_without_code_returns_network_error(self) -> None:
        adapter = _adapter(max_retries=0)

        class PlainOSError(OSError):
            pass

        with patch("httpx.Client.post", side_effect=PlainOSError("socket closed")):
            result = adapter.execute(_make_request())

        self.assertEqual(result.failure_code, FailureCode.PROVIDER_UNAVAILABLE)
        assert result.failure_message is not None
        self.assertIn("network error", result.failure_message)

    def test_os_error_503_retries_and_calls_backoff(self) -> None:
        adapter = _adapter(max_retries=1)
        err = OSError("http 503")
        err.code = 503  # type: ignore[attr-defined]
        responses = [err, _mock_httpx_response({"choices": [{"message": {"content": "Recovered"}}]})]

        with patch("httpx.Client.post", side_effect=responses), patch.object(
            adapter, "_sleep_before_retry"
        ) as sleep_mock:
            result = adapter.execute(_make_request())

        self.assertEqual(result.status, StepStatus.COMPLETED)
        sleep_mock.assert_called_once_with(1)


class PipelineCoverageGapTests(unittest.TestCase):
    def test_multi_model_empty_responses_falls_back_to_single_model_answer(self) -> None:
        from gracekelly.api.routes import pipeline as pipeline_module

        app = _pipeline_app()
        client = TestClient(app)
        empty_result = MagicMock()
        empty_result.responses = []
        empty_result.failed_models = []
        empty_result.model_ids = []

        with patch.object(pipeline_module.MultiModelExecutor, "execute_all", return_value=empty_result):
            response = client.post("/api/v1/pipeline", json={"prompt": "Hello", "multi_model": True})

        self.assertEqual(200, response.status_code)
        body = response.json()
        self.assertEqual(body["answer"], "Fallback answer")
        self.assertEqual(body["models_used"], ["mistral-small"])


class StorageBaseCoverageGapTests(unittest.TestCase):
    def test_list_events_paginated_without_limit_returns_offset_slice_and_total(self) -> None:
        repo = _BaseRepo()
        now = datetime(2026, 1, 1, tzinfo=UTC)
        for seq in range(3):
            repo.append_event(
                TaskEventRecord(
                    event_id=f"e-{seq}",
                    task_id="t1",
                    sequence_no=seq,
                    event_type=EventType.TASK_COMPLETED,
                    created_at=now,
                )
            )

        page, total = repo.list_events_paginated("t1", offset=1)
        self.assertEqual(total, 3)
        self.assertEqual([event.sequence_no for event in page], [1, 2])


if __name__ == "__main__":
    unittest.main()
