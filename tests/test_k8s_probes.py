from __future__ import annotations

import unittest

from fastapi.testclient import TestClient

from gracekelly.config import Settings
from gracekelly.main import create_app


def _make_settings(require_auth: bool = False) -> Settings:
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
        require_auth=require_auth,
    )


class LivenessProbeTests(unittest.TestCase):
    def test_liveness_returns_200(self) -> None:
        client = TestClient(create_app(_make_settings()))
        resp = client.get("/healthz/live")
        self.assertEqual(resp.status_code, 200)

    def test_liveness_returns_ok_status(self) -> None:
        client = TestClient(create_app(_make_settings()))
        resp = client.get("/healthz/live")
        self.assertEqual(resp.json()["status"], "ok")

    def test_liveness_allows_strict_auth_without_key(self) -> None:
        client = TestClient(create_app(_make_settings(require_auth=True)))
        resp = client.get("/healthz/live")
        self.assertEqual(resp.status_code, 200)


class ReadinessProbeTests(unittest.TestCase):
    def test_readiness_returns_200_with_memory_storage(self) -> None:
        client = TestClient(create_app(_make_settings()))
        resp = client.get("/healthz/ready")
        self.assertEqual(resp.status_code, 200)

    def test_readiness_includes_storage_backend(self) -> None:
        client = TestClient(create_app(_make_settings()))
        resp = client.get("/healthz/ready")
        self.assertIn("storage", resp.json())


if __name__ == "__main__":
    unittest.main()
