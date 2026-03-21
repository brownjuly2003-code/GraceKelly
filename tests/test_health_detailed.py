from __future__ import annotations

import unittest
from unittest.mock import MagicMock

from fastapi import FastAPI
from fastapi.testclient import TestClient

from gracekelly.api.routes.health_detailed import router


def _create_test_app(
    *,
    adapters_with_keys: bool = True,
    has_embeddings: bool = True,
    embeddings_has_key: bool = True,
) -> FastAPI:
    app = FastAPI()
    app.include_router(router)

    adapter_a = MagicMock()
    adapter_b = MagicMock()
    if adapters_with_keys:
        adapter_a._api_key = "key-a"
        adapter_b._api_key = "key-b"
    else:
        adapter_a._api_key = None
        adapter_b._api_key = None
    app.state.api_adapters = {"mistral": adapter_a, "openai": adapter_b}

    if has_embeddings:
        embeddings = MagicMock()
        embeddings.cache_size.return_value = 42
        if embeddings_has_key:
            embeddings._api_key = "embed-key"
        else:
            embeddings._api_key = None
        app.state.embeddings_client = embeddings
    else:
        app.state.embeddings_client = None

    return app


class HealthDetailedTests(unittest.TestCase):
    def test_healthy_with_keys_and_embeddings(self) -> None:
        client = TestClient(_create_test_app())
        response = client.get("/api/v1/health/detailed")
        self.assertEqual(200, response.status_code)
        body = response.json()
        self.assertEqual("healthy", body["status"])

    def test_degraded_without_keys(self) -> None:
        client = TestClient(_create_test_app(adapters_with_keys=False))
        response = client.get("/api/v1/health/detailed")
        body = response.json()
        self.assertEqual("degraded", body["status"])

    def test_degraded_without_embeddings(self) -> None:
        client = TestClient(_create_test_app(has_embeddings=False))
        response = client.get("/api/v1/health/detailed")
        body = response.json()
        self.assertEqual("degraded", body["status"])

    def test_uptime_seconds_non_negative(self) -> None:
        client = TestClient(_create_test_app())
        response = client.get("/api/v1/health/detailed")
        body = response.json()
        self.assertGreaterEqual(body["uptime_seconds"], 0)

    def test_total_adapters_matches_count(self) -> None:
        client = TestClient(_create_test_app())
        response = client.get("/api/v1/health/detailed")
        body = response.json()
        self.assertEqual(2, body["total_adapters"])
        self.assertEqual(2, len(body["adapters"]))

    def test_adapter_names_in_response(self) -> None:
        client = TestClient(_create_test_app())
        response = client.get("/api/v1/health/detailed")
        body = response.json()
        names = {a["name"] for a in body["adapters"]}
        self.assertEqual({"mistral", "openai"}, names)

    def test_embeddings_cache_size(self) -> None:
        client = TestClient(_create_test_app())
        response = client.get("/api/v1/health/detailed")
        body = response.json()
        self.assertEqual(42, body["embeddings"]["cache_size"])

    def test_degraded_when_embeddings_no_key(self) -> None:
        client = TestClient(
            _create_test_app(embeddings_has_key=False),
        )
        response = client.get("/api/v1/health/detailed")
        body = response.json()
        self.assertEqual("degraded", body["status"])


if __name__ == "__main__":
    unittest.main()
