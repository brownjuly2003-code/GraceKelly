from __future__ import annotations

import unittest
from unittest.mock import MagicMock

from fastapi import FastAPI
from fastapi.testclient import TestClient

from gracekelly.api.routes.debate import router
from gracekelly.core.contracts import StepStatus


def _create_test_app() -> FastAPI:
    app = FastAPI()
    app.include_router(router)

    adapter = MagicMock()
    adapter.execute.return_value = MagicMock(
        status=StepStatus.COMPLETED,
        output_text="Mocked LLM response",
        failure_code=None,
        failure_message=None,
    )
    app.state.api_adapters = {"mistral": adapter}
    return app


class DebateRouteTests(unittest.TestCase):
    def test_debate_returns_200(self) -> None:
        client = TestClient(_create_test_app())
        response = client.post("/api/v1/debate", json={"topic": "AI safety"})
        self.assertEqual(200, response.status_code)

    def test_debate_response_fields(self) -> None:
        client = TestClient(_create_test_app())
        response = client.post("/api/v1/debate", json={"topic": "AI safety"})
        body = response.json()
        for field in (
            "initial_position",
            "challenge",
            "defense",
            "improved_response",
            "model_id",
            "total_llm_calls",
        ):
            self.assertIn(field, body)
            self.assertTrue(body[field], f"{field} should be non-empty")

    def test_debate_with_initial_position(self) -> None:
        client = TestClient(_create_test_app())
        response = client.post(
            "/api/v1/debate",
            json={"topic": "AI safety", "initial_position": "AI is safe"},
        )
        body = response.json()
        self.assertEqual(200, response.status_code)
        self.assertEqual("AI is safe", body["initial_position"])

    def test_debate_without_initial_position(self) -> None:
        app = _create_test_app()
        client = TestClient(app)
        response = client.post("/api/v1/debate", json={"topic": "AI safety"})
        self.assertEqual(200, response.status_code)
        adapter = app.state.api_adapters["mistral"]
        self.assertEqual(3, adapter.execute.call_count)

    def test_debate_with_initial_position_calls(self) -> None:
        app = _create_test_app()
        client = TestClient(app)
        response = client.post(
            "/api/v1/debate",
            json={"topic": "AI safety", "initial_position": "AI is safe"},
        )
        self.assertEqual(200, response.status_code)
        adapter = app.state.api_adapters["mistral"]
        self.assertEqual(2, adapter.execute.call_count)

    def test_debate_invalid_model_400(self) -> None:
        client = TestClient(_create_test_app())
        response = client.post(
            "/api/v1/debate",
            json={"topic": "AI safety", "model": "nonexistent-model-xyz"},
        )
        self.assertEqual(400, response.status_code)

    def test_debate_model_id_in_response(self) -> None:
        client = TestClient(_create_test_app())
        response = client.post("/api/v1/debate", json={"topic": "AI safety"})
        body = response.json()
        self.assertEqual("mistral-small", body["model_id"])

    def test_debate_total_llm_calls(self) -> None:
        client = TestClient(_create_test_app())
        response = client.post(
            "/api/v1/debate",
            json={"topic": "AI safety", "initial_position": "AI is safe"},
        )
        body = response.json()
        self.assertEqual(2, body["total_llm_calls"])

    def test_debate_total_llm_calls_without_initial(self) -> None:
        client = TestClient(_create_test_app())
        response = client.post("/api/v1/debate", json={"topic": "AI safety"})
        body = response.json()
        self.assertEqual(3, body["total_llm_calls"])

    def test_debate_empty_topic_returns_422(self) -> None:
        client = TestClient(_create_test_app())
        response = client.post("/api/v1/debate", json={"topic": ""})
        self.assertEqual(422, response.status_code)


if __name__ == "__main__":
    unittest.main()
