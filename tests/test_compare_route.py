from __future__ import annotations

import unittest
from unittest.mock import MagicMock

from fastapi import FastAPI
from fastapi.testclient import TestClient

from gracekelly.api.routes.compare import router
from gracekelly.core.contracts import StepStatus


def _make_adapter(*, output_text: str = "Test answer") -> MagicMock:
    adapter = MagicMock()
    adapter.execute.return_value = MagicMock(
        status=StepStatus.COMPLETED,
        output_text=output_text,
        failure_code=None,
        failure_message=None,
    )
    return adapter


def _create_test_app(adapters: dict[str, MagicMock] | None = None) -> FastAPI:
    app = FastAPI()
    app.include_router(router)
    app.state.api_adapters = adapters or {"mistral": _make_adapter()}
    return app


class CompareRouteTests(unittest.TestCase):
    def test_single_model_200(self) -> None:
        client = TestClient(_create_test_app())
        resp = client.post("/api/v1/compare", json={
            "prompt": "What is Python?",
            "models": ["mistral-small"],
        })
        self.assertEqual(200, resp.status_code)
        body = resp.json()
        self.assertEqual(1, len(body["answers"]))
        self.assertEqual("completed", body["answers"][0]["status"])

    def test_multiple_models_same_provider(self) -> None:
        adapter = _make_adapter()
        client = TestClient(_create_test_app({"mistral": adapter}))
        resp = client.post("/api/v1/compare", json={
            "prompt": "Hello",
            "models": ["mistral-small", "mistral-small"],
            "analyze": False,
        })
        self.assertEqual(200, resp.status_code)
        body = resp.json()
        self.assertEqual(2, len(body["answers"]))
        self.assertEqual(2, adapter.execute.call_count)

    def test_response_has_all_fields(self) -> None:
        client = TestClient(_create_test_app())
        resp = client.post("/api/v1/compare", json={
            "prompt": "Hello",
            "models": ["mistral-small"],
        })
        body = resp.json()
        self.assertIn("answers", body)
        self.assertIn("analysis", body)
        self.assertIn("total_models", body)
        self.assertIn("succeeded", body)
        self.assertIn("failed", body)

    def test_invalid_model_graceful(self) -> None:
        client = TestClient(_create_test_app())
        resp = client.post("/api/v1/compare", json={
            "prompt": "Hello",
            "models": ["totally-fake-model-xyz"],
        })
        self.assertEqual(200, resp.status_code)
        body = resp.json()
        self.assertEqual(1, len(body["answers"]))
        self.assertEqual("unknown_model", body["answers"][0]["status"])
        self.assertEqual(0, body["succeeded"])
        self.assertEqual(1, body["failed"])

    def test_no_analysis_when_single_model(self) -> None:
        client = TestClient(_create_test_app())
        resp = client.post("/api/v1/compare", json={
            "prompt": "Hello",
            "models": ["mistral-small"],
            "analyze": True,
        })
        body = resp.json()
        self.assertIsNone(body["analysis"])

    def test_analysis_when_multiple(self) -> None:
        adapter = _make_adapter(output_text="Analysis result")
        client = TestClient(_create_test_app({"mistral": adapter}))
        resp = client.post("/api/v1/compare", json={
            "prompt": "Hello",
            "models": ["mistral-small", "mistral-small"],
            "analyze": True,
        })
        body = resp.json()
        self.assertIsNotNone(body["analysis"])
        self.assertEqual("Analysis result", body["analysis"])

    def test_analyze_false(self) -> None:
        adapter = _make_adapter()
        client = TestClient(_create_test_app({"mistral": adapter}))
        resp = client.post("/api/v1/compare", json={
            "prompt": "Hello",
            "models": ["mistral-small", "mistral-small"],
            "analyze": False,
        })
        body = resp.json()
        self.assertIsNone(body["analysis"])
        self.assertEqual(2, adapter.execute.call_count)

    def test_succeeded_failed_counts(self) -> None:
        adapter = _make_adapter()
        client = TestClient(_create_test_app({"mistral": adapter}))
        resp = client.post("/api/v1/compare", json={
            "prompt": "Hello",
            "models": ["mistral-small", "totally-fake-xyz", "mistral-small"],
        })
        body = resp.json()
        self.assertEqual(3, body["total_models"])
        self.assertEqual(2, body["succeeded"])
        self.assertEqual(1, body["failed"])

    def test_empty_models_validation(self) -> None:
        client = TestClient(_create_test_app())
        resp = client.post("/api/v1/compare", json={
            "prompt": "Hello",
            "models": [],
        })
        self.assertEqual(422, resp.status_code)


if __name__ == "__main__":
    unittest.main()
