from __future__ import annotations

import unittest
from unittest.mock import MagicMock

from fastapi import FastAPI
from fastapi.testclient import TestClient

from gracekelly.api.routes.pipeline import router
from gracekelly.core.contracts import StepStatus


def _create_test_app() -> FastAPI:
    app = FastAPI()
    app.include_router(router)

    adapter = MagicMock()
    adapter.execute.return_value = MagicMock(
        status=StepStatus.COMPLETED,
        output_text="Pipeline answer",
        failure_code=None,
        failure_message=None,
    )
    app.state.api_adapters = {"mistral": adapter}
    return app


class PipelineRouteTests(unittest.TestCase):
    def test_basic_prompt_returns_200(self) -> None:
        client = TestClient(_create_test_app())
        response = client.post("/api/v1/pipeline", json={"prompt": "Hello"})
        self.assertEqual(200, response.status_code)

    def test_task_type_populated(self) -> None:
        client = TestClient(_create_test_app())
        response = client.post(
            "/api/v1/pipeline",
            json={"prompt": "Write Python code"},
        )
        body = response.json()
        self.assertEqual("coding", body["task_type"])

    def test_reliability_level_override(self) -> None:
        client = TestClient(_create_test_app())
        response = client.post(
            "/api/v1/pipeline",
            json={"prompt": "Hello", "reliability_level": "standard"},
        )
        body = response.json()
        self.assertEqual("standard", body["reliability_level"])

    def test_invalid_model_returns_400(self) -> None:
        client = TestClient(_create_test_app())
        response = client.post(
            "/api/v1/pipeline",
            json={"prompt": "Hello", "model": "nonexistent-xyz"},
        )
        self.assertEqual(400, response.status_code)

    def test_invalid_reliability_level_returns_400(self) -> None:
        client = TestClient(_create_test_app())
        response = client.post(
            "/api/v1/pipeline",
            json={"prompt": "Hello", "reliability_level": "ultra"},
        )
        self.assertEqual(400, response.status_code)

    def test_response_has_all_fields(self) -> None:
        client = TestClient(_create_test_app())
        response = client.post("/api/v1/pipeline", json={"prompt": "Hello"})
        body = response.json()
        expected_fields = {
            "answer", "task_type", "pattern_used",
            "reliability_level", "total_llm_calls", "model_id",
            "models_used",
        }
        self.assertEqual(expected_fields, set(body.keys()))

    def test_total_llm_calls_at_least_one(self) -> None:
        client = TestClient(_create_test_app())
        response = client.post("/api/v1/pipeline", json={"prompt": "Hello"})
        body = response.json()
        self.assertGreaterEqual(body["total_llm_calls"], 1)

    def test_model_id_in_response(self) -> None:
        client = TestClient(_create_test_app())
        response = client.post("/api/v1/pipeline", json={"prompt": "Hello"})
        body = response.json()
        self.assertEqual("mistral-small", body["model_id"])

    def test_multi_model_flag_accepted(self) -> None:
        client = TestClient(_create_test_app())
        response = client.post(
            "/api/v1/pipeline",
            json={"prompt": "Hello", "multi_model": True},
        )
        self.assertEqual(200, response.status_code)
        body = response.json()
        self.assertIsInstance(body["models_used"], list)
        self.assertGreater(len(body["models_used"]), 0)

    def test_general_task_type_for_simple_prompt(self) -> None:
        client = TestClient(_create_test_app())
        response = client.post(
            "/api/v1/pipeline",
            json={"prompt": "What is the weather today?"},
        )
        body = response.json()
        self.assertEqual("general", body["task_type"])

    def test_pipeline_missing_adapter_returns_400(self) -> None:
        # "Claude Sonnet 4.6 API" uses provider "anthropic"; only "mistral" is registered
        client = TestClient(_create_test_app())
        response = client.post(
            "/api/v1/pipeline",
            json={"prompt": "Hello", "model": "Claude Sonnet 4.6 API"},
        )
        self.assertEqual(400, response.status_code)
        self.assertIn("No adapter", response.json()["detail"])

    def test_pipeline_complex_prompt_resolves_standard_reliability(self) -> None:
        # Prompt with many complexity indicators scores >= 0.6 → COMPLEX → STANDARD reliability
        complex_prompt = (
            "compare analyze evaluate comprehensive step by step different perspectives "
            "detailed analysis implications consequences advantages and disadvantages critically assess"
        )
        client = TestClient(_create_test_app())
        response = client.post("/api/v1/pipeline", json={"prompt": complex_prompt})
        body = response.json()
        self.assertEqual(200, response.status_code)
        self.assertEqual("standard", body["reliability_level"])

    def test_pipeline_failed_result_uses_error_fallback(self) -> None:
        app = FastAPI()
        app.include_router(router)
        adapter = MagicMock()
        adapter.execute.return_value = MagicMock(
            status=StepStatus.FAILED,
            output_text=None,
            failure_code="timeout",
            failure_message="Request timed out",
        )
        app.state.api_adapters = {"mistral": adapter}
        client = TestClient(app)

        response = client.post("/api/v1/pipeline", json={"prompt": "Hello"})
        body = response.json()

        self.assertEqual(200, response.status_code)
        self.assertIn("[timeout]", body["answer"])


if __name__ == "__main__":
    unittest.main()
