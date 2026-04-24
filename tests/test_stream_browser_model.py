from __future__ import annotations

import json
import unittest
from collections.abc import Callable, Iterator
from concurrent.futures import Future
from types import SimpleNamespace
from typing import Any
from unittest.mock import Mock

from fastapi import FastAPI
from fastapi.testclient import TestClient

from gracekelly.config import Settings
from gracekelly.core.contracts import StreamChunk
from gracekelly.main import create_app


class StreamBrowserModelTests(unittest.TestCase):
    def setUp(self) -> None:
        self.app: FastAPI = create_app(
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
        self.client = TestClient(self.app)

    def _collect_sse(self, response: Any) -> list[dict[str, Any]]:
        events: list[dict[str, Any]] = []
        event_type = ""
        for line in response.text.splitlines():
            if line.startswith("event: "):
                event_type = line[7:].strip()
            elif line.startswith("data: "):
                data = json.loads(line[6:].strip())
                if event_type:
                    events.append({"type": event_type, "data": data})
                    event_type = ""
        return events

    def test_browser_model_stream_returns_accepted_and_complete_events(self) -> None:
        snapshot = SimpleNamespace(
            task=SimpleNamespace(task_id="browser-task-1", output_text="browser result", duration_ms=17),
            steps=[SimpleNamespace(input_tokens=3, output_tokens=5)],
        )
        submit_snapshot = Mock(return_value=snapshot)
        self.app.state.orchestrator_service.submit_snapshot = submit_snapshot

        class RecordingExecutor:
            def __init__(self) -> None:
                self.fn: Callable[..., Any] | None = None
                self.args: tuple[Any, ...] = ()

            def submit(self, fn: Callable[..., Any], /, *args: Any, **kwargs: Any) -> Future[Any]:
                self.fn = fn
                self.args = args
                future: Future[Any] = Future()
                future.set_result(fn(*args, **kwargs))
                return future

        self.app.state.browser_executor = RecordingExecutor()

        response = self.client.post(
            "/api/v1/orchestrate/stream",
            json={"prompt": "hello", "model": "Best", "dry_run": False},
        )

        self.assertEqual(response.status_code, 200)
        self.assertIn("text/event-stream", response.headers.get("content-type", ""))
        events = self._collect_sse(response)
        self.assertEqual([event["type"] for event in events], ["accepted", "complete"])
        self.assertEqual(events[0]["data"]["task_id"], "browser-task-1")
        self.assertEqual(events[1]["data"]["task_id"], "browser-task-1")
        self.assertEqual(events[1]["data"]["text"], "browser result")
        self.assertEqual(events[1]["data"]["input_tokens"], 3)
        self.assertEqual(events[1]["data"]["output_tokens"], 5)
        self.assertTrue(submit_snapshot.called)

    def test_browser_model_stream_uses_browser_executor_for_submit_snapshot(self) -> None:
        snapshot = SimpleNamespace(
            task=SimpleNamespace(task_id="browser-task-2", output_text="browser executor", duration_ms=9),
            steps=[],
        )
        submit_snapshot = Mock(return_value=snapshot)
        self.app.state.orchestrator_service.submit_snapshot = submit_snapshot

        class RecordingExecutor:
            def __init__(self) -> None:
                self.fn: Callable[..., Any] | None = None
                self.args: tuple[Any, ...] = ()

            def submit(self, fn: Callable[..., Any], /, *args: Any, **kwargs: Any) -> Future[Any]:
                self.fn = fn
                self.args = args
                future: Future[Any] = Future()
                future.set_result(fn(*args, **kwargs))
                return future

        recording_executor = RecordingExecutor()
        self.app.state.browser_executor = recording_executor

        response = self.client.post(
            "/api/v1/orchestrate/stream",
            json={"prompt": "hello", "model": "Best", "dry_run": False},
        )

        self.assertEqual(response.status_code, 200)
        self.assertIs(recording_executor.fn, submit_snapshot)
        self.assertEqual(len(recording_executor.args), 1)
        self.assertEqual(recording_executor.args[0].prompt, "hello")
        self.assertEqual(recording_executor.args[0].model, "Best")

    def test_api_model_stream_still_uses_streaming_adapter(self) -> None:
        class StreamingAdapter:
            name = "api.openai"

            def execute_stream(self, request: Any) -> Iterator[StreamChunk]:
                yield StreamChunk(type="delta", text="stream ", model_id=request.step.model.id)
                yield StreamChunk(
                    type="complete",
                    text="api result",
                    model_id=request.step.model.id,
                    details={"duration_ms": 7, "input_tokens": 11, "output_tokens": 13},
                )

        self.app.state.api_adapters["openai"] = StreamingAdapter()

        response = self.client.post(
            "/api/v1/orchestrate/stream",
            json={"prompt": "hello", "model": "GPT-5.4 API", "dry_run": False},
        )

        self.assertEqual(response.status_code, 200)
        self.assertIn("text/event-stream", response.headers.get("content-type", ""))
        events = self._collect_sse(response)
        self.assertEqual([event["type"] for event in events], ["accepted", "delta", "complete"])
        self.assertEqual(events[-1]["data"]["text"], "api result")
