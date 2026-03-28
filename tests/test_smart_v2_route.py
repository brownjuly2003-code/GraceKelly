from __future__ import annotations

import unittest
from unittest.mock import MagicMock

from fastapi import FastAPI
from fastapi.testclient import TestClient

from gracekelly.api.routes.smart_v2 import router
from gracekelly.core.contracts import StepStatus
from gracekelly.core.embeddings import EmbeddingsClient


def _create_test_app(*, has_embeddings: bool = True) -> FastAPI:
    app = FastAPI()
    app.include_router(router)

    adapter = MagicMock()
    adapter.execute.return_value = MagicMock(
        status=StepStatus.COMPLETED,
        output_text="Test response. Confidence: 8/10",
        failure_code=None,
        failure_message=None,
    )
    app.state.api_adapters = {"mistral": adapter}

    if has_embeddings:
        embeddings = MagicMock(spec=EmbeddingsClient)
        embeddings.embed.return_value = [1.0, 0.0, 0.0]
        embeddings.embed_batch.side_effect = lambda texts: [[1.0, 0.0, 0.0] for _ in texts]
        app.state.embeddings_client = embeddings
    else:
        app.state.embeddings_client = None

    return app


class SmartV2RouteTests(unittest.TestCase):
    def test_simple_prompt_returns_200(self) -> None:
        client = TestClient(_create_test_app())
        response = client.post("/api/v1/smart/v2", json={"prompt": "Hello"})
        self.assertEqual(200, response.status_code)

    def test_response_has_v2_fields(self) -> None:
        client = TestClient(_create_test_app())
        response = client.post("/api/v1/smart/v2", json={"prompt": "Hello"})
        body = response.json()
        self.assertIn("consensus_status", body)
        self.assertIn("consensus_score", body)
        self.assertIn("cluster_confidence", body)
        self.assertIn("dissenting_views", body)

    def test_simple_prompt_no_consensus(self) -> None:
        client = TestClient(_create_test_app())
        response = client.post("/api/v1/smart/v2", json={"prompt": "Hello"})
        body = response.json()
        self.assertIsNone(body["consensus_status"])
        self.assertIsNone(body["consensus_score"])

    def test_consensus_fields_on_standard_level(self) -> None:
        client = TestClient(_create_test_app())
        response = client.post(
            "/api/v1/smart/v2",
            json={"prompt": "Hello", "reliability_level": "standard"},
        )
        body = response.json()
        self.assertEqual(200, response.status_code)
        self.assertIn("consensus_status", body)
        self.assertIn("consensus_score", body)
        self.assertIn("cluster_confidence", body)

    def test_dissenting_views_is_list(self) -> None:
        client = TestClient(_create_test_app())
        response = client.post("/api/v1/smart/v2", json={"prompt": "Hello"})
        body = response.json()
        self.assertIsInstance(body["dissenting_views"], list)

    def test_task_type_detection(self) -> None:
        client = TestClient(_create_test_app())
        response = client.post(
            "/api/v1/smart/v2",
            json={"prompt": "Write Python code"},
        )
        body = response.json()
        self.assertEqual("coding", body["task_type"])

    def test_invalid_model_returns_400(self) -> None:
        client = TestClient(_create_test_app())
        response = client.post(
            "/api/v1/smart/v2",
            json={"prompt": "Hello", "model": "nonexistent"},
        )
        self.assertEqual(400, response.status_code)

    def test_both_level_and_pattern_returns_400(self) -> None:
        client = TestClient(_create_test_app())
        response = client.post(
            "/api/v1/smart/v2",
            json={
                "prompt": "Hello",
                "reliability_level": "quick",
                "pattern": "single",
            },
        )
        self.assertEqual(400, response.status_code)

    def test_pattern_override_works(self) -> None:
        client = TestClient(_create_test_app())
        response = client.post(
            "/api/v1/smart/v2",
            json={"prompt": "Hello", "pattern": "single"},
        )
        body = response.json()
        self.assertEqual("single", body["pattern_used"])

    def test_model_id_in_response(self) -> None:
        client = TestClient(_create_test_app())
        response = client.post("/api/v1/smart/v2", json={"prompt": "Hello"})
        body = response.json()
        self.assertIsInstance(body["model_id"], str)
        self.assertTrue(body["model_id"])

    def test_complexity_level_present(self) -> None:
        client = TestClient(_create_test_app())
        response = client.post("/api/v1/smart/v2", json={"prompt": "Hello"})
        body = response.json()
        self.assertIn(body["complexity_level"], ("simple", "moderate", "complex"))

    def test_total_llm_calls_positive(self) -> None:
        client = TestClient(_create_test_app())
        response = client.post("/api/v1/smart/v2", json={"prompt": "Hello"})
        body = response.json()
        self.assertGreaterEqual(body["total_llm_calls"], 1)

    def test_no_embeddings_falls_back(self) -> None:
        client = TestClient(_create_test_app(has_embeddings=False))
        response = client.post(
            "/api/v1/smart/v2",
            json={"prompt": "Hello", "pattern": "consensus"},
        )
        self.assertEqual(200, response.status_code)

    def test_smart_v2_missing_adapter_returns_400(self) -> None:
        # "Claude Sonnet 4.6 API" uses provider "anthropic"; only "mistral" is registered
        client = TestClient(_create_test_app())
        response = client.post(
            "/api/v1/smart/v2",
            json={"prompt": "Hello", "model": "Claude Sonnet 4.6 API"},
        )
        self.assertEqual(400, response.status_code)
        self.assertIn("No API adapter", response.json()["detail"])

    def test_smart_v2_failed_result_returns_error_answer(self) -> None:
        app = _create_test_app()
        app.state.api_adapters["mistral"].execute.return_value = MagicMock(
            status=StepStatus.FAILED,
            output_text=None,
            failure_code="timeout",
            failure_message="Request timed out",
        )
        client = TestClient(app)
        response = client.post("/api/v1/smart/v2", json={"prompt": "Hello", "pattern": "single"})
        self.assertEqual(200, response.status_code)
        self.assertIn("[timeout]", response.json()["answer"])


if __name__ == "__main__":
    unittest.main()
