from __future__ import annotations

import hashlib
import json
import pathlib
import tempfile
import unittest
from typing import IO, Any
from unittest.mock import patch

from fastapi import FastAPI
from fastapi.testclient import TestClient

from gracekelly.middleware import setup_usage_telemetry


def _build_app(log_path: str | None, *, enabled: bool) -> FastAPI:
    app = FastAPI()

    @app.get("/health")
    async def health() -> dict[str, bool]:
        return {"ok": True}

    @app.post("/api/v1/orchestrate")
    async def orchestrate() -> dict[str, str]:
        return {"task_id": "abc"}

    @app.post("/api/v1/consensus")
    async def consensus() -> dict[str, str]:
        return {"task_id": "def"}

    @app.post("/api/v1/tasks/123e4567-e89b-12d3-a456-426614174000/retry")
    async def retry() -> dict[str, bool]:
        return {"ok": True}

    setup_usage_telemetry(app, enabled=enabled, log_path=log_path)
    return app


class UsageTelemetryDisabledTests(unittest.TestCase):
    def test_no_op_when_disabled_writes_nothing(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            log_path = pathlib.Path(tmp) / "usage.jsonl"
            app = _build_app(str(log_path), enabled=False)
            client = TestClient(app)
            response = client.get("/health")
            self.assertEqual(response.status_code, 200)
            self.assertFalse(log_path.exists())


class UsageTelemetryEnabledTests(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.log_path = pathlib.Path(self._tmp.name) / "usage.jsonl"
        self.app = _build_app(str(self.log_path), enabled=True)
        self.client = TestClient(self.app)

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def _read_lines(self) -> list[dict[str, object]]:
        if not self.log_path.exists():
            return []
        text = self.log_path.read_text(encoding="utf-8")
        return [json.loads(line) for line in text.splitlines() if line.strip()]

    def test_one_line_appended_per_request(self) -> None:
        self.client.get("/health")
        self.client.get("/health")
        self.client.post("/api/v1/orchestrate", json={"prompt": "hi"})
        records = self._read_lines()
        self.assertEqual(len(records), 3)

    def test_record_carries_seven_keys(self) -> None:
        self.client.get("/health")
        records = self._read_lines()
        self.assertEqual(
            set(records[0].keys()),
            {"ts", "endpoint", "method", "status", "duration_ms", "request_id", "prompt_hash"},
        )

    def test_endpoint_uuid_segments_normalised(self) -> None:
        self.client.post(
            "/api/v1/tasks/123e4567-e89b-12d3-a456-426614174000/retry",
            json={"prompt": "x"},
        )
        records = self._read_lines()
        self.assertEqual(records[0]["endpoint"], "/api/v1/tasks/{id}/retry")

    def test_prompt_hash_present_for_orchestrate_post(self) -> None:
        body_bytes = b'{"prompt":"what is 2+2"}'
        self.client.post(
            "/api/v1/orchestrate",
            content=body_bytes,
            headers={"content-type": "application/json"},
        )
        records = self._read_lines()
        self.assertEqual(records[0]["prompt_hash"], hashlib.sha256(body_bytes).hexdigest())

    def test_prompt_hash_present_for_consensus_post(self) -> None:
        body = {"prompt": "x", "models": ["a", "b"]}
        self.client.post("/api/v1/consensus", json=body)
        records = self._read_lines()
        self.assertIsNotNone(records[0]["prompt_hash"])

    def test_prompt_hash_null_for_health_get(self) -> None:
        self.client.get("/health")
        records = self._read_lines()
        self.assertIsNone(records[0]["prompt_hash"])

    def test_prompt_hash_null_for_non_orchestration_post(self) -> None:
        self.client.post(
            "/api/v1/tasks/123e4567-e89b-12d3-a456-426614174000/retry",
            json={"prompt": "x"},
        )
        records = self._read_lines()
        self.assertIsNone(records[0]["prompt_hash"])

    def test_request_id_picked_up_from_response_header(self) -> None:
        self.client.get("/health", headers={"X-Request-ID": "trace-abc-123"})
        records = self._read_lines()
        self.assertEqual(records[0]["request_id"], "trace-abc-123")

    def test_request_id_null_when_neither_header_set(self) -> None:
        self.client.get("/health")
        records = self._read_lines()
        self.assertIsNone(records[0]["request_id"])

    def test_status_and_method_recorded(self) -> None:
        self.client.post("/api/v1/orchestrate", json={"prompt": "x"})
        records = self._read_lines()
        self.assertEqual(records[0]["method"], "POST")
        self.assertEqual(records[0]["status"], 200)

    def test_body_is_replayed_to_downstream_handler(self) -> None:
        body = {"prompt": "downstream-must-see-me"}
        response = self.client.post("/api/v1/consensus", json=body)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"task_id": "def"})

    def test_write_failure_does_not_break_response(self) -> None:
        original_open = pathlib.Path.open

        def _failing_open(
            self_path: pathlib.Path,
            mode: str = "r",
            buffering: int = -1,
            encoding: str | None = None,
            errors: str | None = None,
            newline: str | None = None,
        ) -> IO[Any]:
            if self_path == self.log_path:
                raise OSError("simulated disk failure")
            return original_open(
                self_path,
                mode=mode,
                buffering=buffering,
                encoding=encoding,
                errors=errors,
                newline=newline,
            )

        with patch.object(pathlib.Path, "open", _failing_open):
            response = self.client.get("/health")
        self.assertEqual(response.status_code, 200)
