from __future__ import annotations

import unittest
from unittest.mock import MagicMock

from fastapi import FastAPI
from fastapi.testclient import TestClient

from gracekelly.api.routes.batch import router
from gracekelly.core.contracts import StepStatus


def _create_test_app(*, adapter_succeeds: bool = True) -> FastAPI:
    app = FastAPI()
    app.include_router(router)

    adapter = MagicMock()
    if adapter_succeeds:
        adapter.execute.return_value = MagicMock(
            status=StepStatus.COMPLETED,
            output_text="Test answer",
            failure_code=None,
            failure_message=None,
        )
    else:
        adapter.execute.return_value = MagicMock(
            status=StepStatus.FAILED,
            output_text=None,
            failure_code="error",
            failure_message="execution failed",
        )
    app.state.api_adapters = {"mistral": adapter}
    return app


class BatchRouteTests(unittest.TestCase):
    def test_single_prompt_returns_200(self) -> None:
        client = TestClient(_create_test_app())
        response = client.post("/api/v1/batch", json={"prompts": ["Hello"]})
        self.assertEqual(200, response.status_code)

    def test_single_prompt_succeeded_count(self) -> None:
        client = TestClient(_create_test_app())
        response = client.post("/api/v1/batch", json={"prompts": ["Hello"]})
        body = response.json()
        self.assertEqual(1, body["succeeded"])
        self.assertEqual(0, body["failed"])
        self.assertEqual(1, body["total"])

    def test_multiple_prompts_all_succeed(self) -> None:
        client = TestClient(_create_test_app())
        prompts = ["Hello", "How are you?", "What is 2+2?"]
        response = client.post("/api/v1/batch", json={"prompts": prompts})
        body = response.json()
        self.assertEqual(3, body["total"])
        self.assertEqual(3, body["succeeded"])
        self.assertEqual(0, body["failed"])
        self.assertEqual(3, len(body["results"]))

    def test_invalid_model_returns_400(self) -> None:
        client = TestClient(_create_test_app())
        response = client.post(
            "/api/v1/batch",
            json={"prompts": ["Hello"], "model": "nonexistent-xyz"},
        )
        self.assertEqual(400, response.status_code)

    def test_failed_execution_status_failed(self) -> None:
        client = TestClient(_create_test_app(adapter_succeeds=False))
        response = client.post("/api/v1/batch", json={"prompts": ["Hello"]})
        body = response.json()
        self.assertEqual(0, body["succeeded"])
        self.assertEqual(1, body["failed"])
        self.assertEqual("failed", body["results"][0]["status"])

    def test_response_has_total_succeeded_failed(self) -> None:
        client = TestClient(_create_test_app())
        response = client.post("/api/v1/batch", json={"prompts": ["Hello"]})
        body = response.json()
        self.assertIn("total", body)
        self.assertIn("succeeded", body)
        self.assertIn("failed", body)
        self.assertIn("results", body)

    def test_empty_prompts_returns_422(self) -> None:
        client = TestClient(_create_test_app())
        response = client.post("/api/v1/batch", json={"prompts": []})
        self.assertEqual(422, response.status_code)

    def test_result_item_has_prompt_and_answer(self) -> None:
        client = TestClient(_create_test_app())
        response = client.post("/api/v1/batch", json={"prompts": ["Hello"]})
        item = response.json()["results"][0]
        self.assertEqual("Hello", item["prompt"])
        self.assertEqual("Test answer", item["answer"])
        self.assertEqual("completed", item["status"])

    def test_adapter_exception_returns_error_status(self) -> None:
        app = FastAPI()
        app.include_router(router)
        adapter = MagicMock()
        adapter.execute.side_effect = RuntimeError("boom")
        app.state.api_adapters = {"mistral": adapter}

        client = TestClient(app)
        response = client.post("/api/v1/batch", json={"prompts": ["Hello"]})
        body = response.json()
        self.assertEqual("error", body["results"][0]["status"])
        self.assertEqual(1, body["failed"])

    def test_missing_adapter_for_provider_returns_400(self) -> None:
        # "Claude Sonnet 4.6 API" uses provider "anthropic"; app only has "mistral"
        client = TestClient(_create_test_app())
        response = client.post(
            "/api/v1/batch",
            json={"prompts": ["Hello"], "model": "Claude Sonnet 4.6 API"},
        )
        self.assertEqual(400, response.status_code)
        self.assertIn("No adapter", response.json()["detail"])

    def test_batch_rejects_unknown_fields(self) -> None:
        client = TestClient(_create_test_app())
        response = client.post(
            "/api/v1/batch",
            json={"prompts": ["Hello"], "dry_run": True},
        )
        self.assertEqual(422, response.status_code)

    def test_completed_with_no_output_text_counts_as_failed(self) -> None:
        app = FastAPI()
        app.include_router(router)
        adapter = MagicMock()
        adapter.execute.return_value = MagicMock(
            status=StepStatus.COMPLETED,
            output_text=None,
            failure_code=None,
            failure_message=None,
        )
        app.state.api_adapters = {"mistral": adapter}
        client = TestClient(app)

        response = client.post("/api/v1/batch", json={"prompts": ["Hello"]})
        body = response.json()

        self.assertEqual(0, body["succeeded"])
        self.assertEqual(1, body["failed"])
        self.assertEqual("failed", body["results"][0]["status"])


if __name__ == "__main__":
    unittest.main()
