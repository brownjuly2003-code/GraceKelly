from __future__ import annotations

import unittest
from unittest.mock import MagicMock

from fastapi import FastAPI
from fastapi.testclient import TestClient

from gracekelly.api.routes.consensus import router
from gracekelly.core.contracts import ExecutionBackend, StepStatus
from gracekelly.core.embeddings import EmbeddingsClient


def _create_test_app(
    *,
    has_embeddings: bool = True,
    has_adapter: bool = True,
    browser_adapter: MagicMock | None = None,
) -> FastAPI:
    app = FastAPI()
    app.include_router(router)

    if has_embeddings:
        embeddings = MagicMock(spec=EmbeddingsClient)
        embeddings.embed.return_value = [1.0, 0.0, 0.0]
        embeddings.embed_batch.side_effect = lambda texts: [[1.0, 0.0, 0.0] for _ in texts]
        app.state.embeddings_client = embeddings
    else:
        app.state.embeddings_client = None

    if has_adapter:
        adapter = MagicMock()
        adapter.execute.return_value = MagicMock(
            status=StepStatus.COMPLETED,
            output_text="Test response. Confidence: 8/10",
            failure_code=None,
            failure_message=None,
        )
        app.state.api_adapters = {"mistral": adapter}
    else:
        app.state.api_adapters = {}
    app.state.browser_adapter = browser_adapter

    return app


class ConsensusRouteTests(unittest.TestCase):
    def test_consensus_returns_200(self) -> None:
        client = TestClient(_create_test_app())
        response = client.post("/api/v1/consensus", json={"prompt": "Hello"})
        self.assertEqual(response.status_code, 200)

    def test_consensus_response_fields(self) -> None:
        client = TestClient(_create_test_app())
        response = client.post("/api/v1/consensus", json={"prompt": "Hello"})
        body = response.json()
        self.assertEqual(
            set(body.keys()),
            {
                "consensus_score",
                "num_clusters",
                "best_response",
                "weighted_score",
                "total_rounds",
                "total_llm_calls",
                "needs_debate",
                "top_cluster_size",
            },
        )

    def test_consensus_score_is_one_for_identical(self) -> None:
        client = TestClient(_create_test_app())
        response = client.post("/api/v1/consensus", json={"prompt": "Hello"})
        self.assertEqual(response.json()["consensus_score"], 1.0)

    def test_total_llm_calls_default_three(self) -> None:
        client = TestClient(_create_test_app())
        response = client.post("/api/v1/consensus", json={"prompt": "Hello"})
        self.assertEqual(response.json()["total_llm_calls"], 3)

    def test_no_embeddings_client_returns_503(self) -> None:
        client = TestClient(_create_test_app(has_embeddings=False))
        response = client.post("/api/v1/consensus", json={"prompt": "Hello"})
        self.assertEqual(response.status_code, 503)

    def test_invalid_model_returns_400(self) -> None:
        client = TestClient(_create_test_app())
        response = client.post(
            "/api/v1/consensus",
            json={"prompt": "Hello", "model": "nonexistent-model-xyz"},
        )
        self.assertEqual(response.status_code, 400)

    def test_custom_threshold(self) -> None:
        client = TestClient(_create_test_app())
        response = client.post(
            "/api/v1/consensus",
            json={"prompt": "Hello", "similarity_threshold": 0.5},
        )
        self.assertEqual(response.status_code, 200)

    def test_weighted_score_present(self) -> None:
        client = TestClient(_create_test_app())
        response = client.post(
            "/api/v1/consensus",
            json={"prompt": "Hello", "use_confidence_weighting": True},
        )
        self.assertIsNotNone(response.json()["weighted_score"])

    def test_weighted_score_absent(self) -> None:
        client = TestClient(_create_test_app())
        response = client.post(
            "/api/v1/consensus",
            json={"prompt": "Hello", "use_confidence_weighting": False},
        )
        self.assertIsNone(response.json()["weighted_score"])

    def test_best_response_not_empty(self) -> None:
        client = TestClient(_create_test_app())
        response = client.post("/api/v1/consensus", json={"prompt": "Hello"})
        self.assertTrue(response.json()["best_response"])

    def test_needs_debate_false_for_identical(self) -> None:
        client = TestClient(_create_test_app())
        response = client.post("/api/v1/consensus", json={"prompt": "Hello"})
        self.assertFalse(response.json()["needs_debate"])

    def test_missing_adapter_returns_400(self) -> None:
        client = TestClient(_create_test_app(has_adapter=False))
        response = client.post("/api/v1/consensus", json={"prompt": "Hello"})
        self.assertEqual(response.status_code, 400)

    def test_browser_model_uses_browser_adapter(self) -> None:
        browser_adapter = MagicMock()
        browser_adapter.execute.return_value = MagicMock(
            status=StepStatus.COMPLETED,
            output_text="Browser response",
            failure_code=None,
            failure_message=None,
        )
        app = _create_test_app(browser_adapter=browser_adapter)
        client = TestClient(app)

        response = client.post("/api/v1/consensus", json={"prompt": "Hello", "model": "best"})
        body = response.json()

        self.assertEqual(200, response.status_code)
        self.assertEqual("Browser response", body["best_response"])
        self.assertEqual(3, browser_adapter.execute.call_count)
        self.assertTrue(
            all(
                call.args[0].step.backend == ExecutionBackend.BROWSER
                for call in browser_adapter.execute.call_args_list
            )
        )
        self.assertEqual(0, app.state.api_adapters["mistral"].execute.call_count)

    def test_browser_model_without_browser_adapter_returns_400(self) -> None:
        client = TestClient(_create_test_app())
        response = client.post("/api/v1/consensus", json={"prompt": "Hello", "model": "best"})
        self.assertEqual(400, response.status_code)
        self.assertIn("No browser adapter", response.json()["detail"])

    def test_executor_exception_returns_500(self) -> None:
        app = _create_test_app()
        app.state.embeddings_client.embed_batch.side_effect = RuntimeError("embedding failure")
        client = TestClient(app, raise_server_exceptions=False)
        response = client.post("/api/v1/consensus", json={"prompt": "Hello"})
        self.assertEqual(500, response.status_code)
        self.assertIn("Consensus execution failed", response.json()["detail"])

    def test_failed_adapter_result_still_returns_200_with_error_text(self) -> None:
        app = _create_test_app()
        app.state.api_adapters["mistral"].execute.return_value = MagicMock(
            status=StepStatus.FAILED,
            output_text=None,
            failure_code="timeout",
            failure_message="Request timed out",
        )
        client = TestClient(app)
        response = client.post("/api/v1/consensus", json={"prompt": "Hello"})
        self.assertEqual(200, response.status_code)
        self.assertIn("[timeout]", response.json()["best_response"])


if __name__ == "__main__":
    unittest.main()
