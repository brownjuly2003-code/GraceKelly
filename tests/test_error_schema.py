from __future__ import annotations

import unittest
import uuid

from fastapi import HTTPException
from fastapi.testclient import TestClient

from gracekelly.config import Settings
from gracekelly.main import create_app


def _make_settings() -> Settings:
    return Settings(
        env="test",
        host="127.0.0.1",
        port=8011,
        log_level="INFO",
        storage_backend="memory",
        postgres_dsn=None,
        mistral_api_key=None,
        mistral_base_url="https://api.mistral.ai/v1",
        mistral_timeout_seconds=30.0,
        openai_api_key=None,
        openai_base_url="https://api.openai.com/v1",
        openai_timeout_seconds=60.0,
        browser_enabled=False,
        browser_profile_dir=None,
        browser_base_url="https://www.perplexity.ai",
    )


class ErrorSchemaTests(unittest.TestCase):
    def setUp(self) -> None:
        app = create_app(_make_settings())

        @app.get("/bad-request")
        def bad_request() -> None:
            raise HTTPException(status_code=400, detail="Bad request")

        self.client = TestClient(app, raise_server_exceptions=False)

    def test_404_has_problem_details_type(self) -> None:
        resp = self.client.get(f"/api/v1/tasks/{uuid.uuid4()}")
        self.assertEqual(resp.status_code, 404)
        self.assertIn("type", resp.json())
        self.assertIn("status", resp.json())

    def test_422_has_problem_details_format(self) -> None:
        resp = self.client.post("/api/v1/orchestrate", json={})
        self.assertEqual(resp.status_code, 422)
        body = resp.json()
        self.assertIn("type", body)
        self.assertIn("title", body)
        self.assertIn("status", body)
        self.assertIn("detail", body)
        self.assertEqual(body["status"], 422)

    def test_400_has_problem_details_format(self) -> None:
        resp = self.client.get("/bad-request")
        self.assertEqual(resp.status_code, 400)
        body = resp.json()
        self.assertIn("type", body)
        self.assertIn("status", body)

    def test_422_detail_mentions_field(self) -> None:
        resp = self.client.post("/api/v1/orchestrate", json={})
        self.assertIn("prompt", resp.json()["detail"])


if __name__ == "__main__":
    unittest.main()
