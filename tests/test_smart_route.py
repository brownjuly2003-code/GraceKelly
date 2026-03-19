from __future__ import annotations

import unittest
from unittest.mock import MagicMock

from fastapi import FastAPI
from fastapi.testclient import TestClient

from gracekelly.api.routes.smart import router
from gracekelly.core.embeddings import EmbeddingsClient
from gracekelly.core.contracts import StepStatus


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


class SmartRouteTests(unittest.TestCase):
    def test_smart_returns_200(self) -> None:
        app = _create_test_app()
        client = TestClient(app)

        response = client.post("/api/v1/smart", json={"prompt": "Hello"})

        self.assertEqual(200, response.status_code)

    def test_smart_response_has_answer(self) -> None:
        app = _create_test_app()
        client = TestClient(app)

        response = client.post("/api/v1/smart", json={"prompt": "Hello"})
        payload = response.json()

        self.assertTrue(payload["answer"])

    def test_smart_auto_detects_task_type(self) -> None:
        app = _create_test_app()
        client = TestClient(app)

        response = client.post("/api/v1/smart", json={"prompt": "Write Python code"})
        payload = response.json()

        self.assertEqual("coding", payload["task_type"])

    def test_smart_simple_prompt_uses_quick(self) -> None:
        app = _create_test_app()
        client = TestClient(app)

        response = client.post("/api/v1/smart", json={"prompt": "What is 2+2?"})
        payload = response.json()

        self.assertEqual("quick", payload["reliability_level"])

    def test_smart_explicit_level(self) -> None:
        app = _create_test_app()
        client = TestClient(app)

        response = client.post(
            "/api/v1/smart",
            json={"prompt": "Hello", "reliability_level": "maximum"},
        )
        payload = response.json()

        self.assertEqual("maximum", payload["reliability_level"])

    def test_smart_explicit_pattern(self) -> None:
        app = _create_test_app()
        client = TestClient(app)

        response = client.post(
            "/api/v1/smart",
            json={"prompt": "Hello", "pattern": "consensus"},
        )
        payload = response.json()

        self.assertEqual("consensus", payload["pattern_used"])

    def test_smart_both_level_and_pattern_returns_400(self) -> None:
        app = _create_test_app()
        client = TestClient(app)

        response = client.post(
            "/api/v1/smart",
            json={"prompt": "Hello", "reliability_level": "quick", "pattern": "single"},
        )

        self.assertEqual(400, response.status_code)

    def test_smart_invalid_model_returns_400(self) -> None:
        app = _create_test_app()
        client = TestClient(app)

        response = client.post(
            "/api/v1/smart",
            json={"prompt": "Hello", "model": "nonexistent"},
        )

        self.assertEqual(400, response.status_code)

    def test_smart_invalid_level_returns_400(self) -> None:
        app = _create_test_app()
        client = TestClient(app)

        response = client.post(
            "/api/v1/smart",
            json={"prompt": "Hello", "reliability_level": "ultra"},
        )

        self.assertEqual(400, response.status_code)

    def test_smart_invalid_pattern_returns_400(self) -> None:
        app = _create_test_app()
        client = TestClient(app)

        response = client.post(
            "/api/v1/smart",
            json={"prompt": "Hello", "pattern": "nonexistent"},
        )

        self.assertEqual(400, response.status_code)

    def test_smart_total_llm_calls_positive(self) -> None:
        app = _create_test_app()
        client = TestClient(app)

        response = client.post("/api/v1/smart", json={"prompt": "Hello"})
        payload = response.json()

        self.assertGreaterEqual(payload["total_llm_calls"], 1)

    def test_smart_model_id_present(self) -> None:
        app = _create_test_app()
        client = TestClient(app)

        response = client.post("/api/v1/smart", json={"prompt": "Hello"})
        payload = response.json()

        self.assertTrue(isinstance(payload["model_id"], str))
        self.assertTrue(payload["model_id"])

    def test_smart_complexity_level_present(self) -> None:
        app = _create_test_app()
        client = TestClient(app)

        response = client.post("/api/v1/smart", json={"prompt": "Hello"})
        payload = response.json()

        self.assertIn(payload["complexity_level"], ("simple", "moderate", "complex"))

    def test_smart_no_embeddings_falls_back(self) -> None:
        app = _create_test_app(has_embeddings=False)
        client = TestClient(app)

        response = client.post(
            "/api/v1/smart",
            json={"prompt": "Hello", "pattern": "consensus"},
        )

        self.assertEqual(200, response.status_code)


if __name__ == "__main__":
    unittest.main()
