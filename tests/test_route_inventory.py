from __future__ import annotations

import unittest

try:
    from fastapi.testclient import TestClient
except ModuleNotFoundError:
    TestClient = None

if TestClient is not None:
    from gracekelly.config import Settings
    from gracekelly.main import create_app


def _make_client() -> "TestClient":
    app = create_app(Settings(
        env="test",
        host="127.0.0.1",
        port=8011,
        log_level="WARNING",
        storage_backend="memory",
        postgres_dsn=None,
        mistral_api_key=None,
        mistral_base_url="https://api.mistral.ai/v1",
        mistral_timeout_seconds=1.0,
        openai_api_key=None,
        openai_base_url="https://api.openai.com/v1",
        openai_timeout_seconds=1.0,
        anthropic_api_key=None,
        anthropic_base_url="https://api.anthropic.com",
        anthropic_timeout_seconds=1.0,
        browser_enabled=False,
        browser_profile_dir=None,
        browser_base_url="https://www.perplexity.ai",
    ))
    return TestClient(app)


@unittest.skipIf(TestClient is None, "fastapi not installed")
class RouteInventoryTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.client = _make_client()

    def test_get_health(self) -> None:
        r = self.client.get("/health")
        self.assertNotEqual(404, r.status_code)

    def test_get_readiness(self) -> None:
        r = self.client.get("/api/v1/readiness")
        self.assertNotEqual(404, r.status_code)

    def test_get_metrics(self) -> None:
        r = self.client.get("/metrics")
        self.assertNotEqual(404, r.status_code)

    def test_get_models(self) -> None:
        r = self.client.get("/api/v1/models")
        self.assertNotEqual(404, r.status_code)

    def test_get_analytics(self) -> None:
        r = self.client.get("/api/v1/analytics")
        self.assertNotEqual(404, r.status_code)

    def test_post_orchestrate(self) -> None:
        r = self.client.post("/api/v1/orchestrate", json={})
        self.assertNotEqual(404, r.status_code)

    def test_post_consensus(self) -> None:
        r = self.client.post("/api/v1/consensus", json={})
        self.assertNotEqual(404, r.status_code)

    def test_post_smart(self) -> None:
        r = self.client.post("/api/v1/smart", json={})
        self.assertNotEqual(404, r.status_code)

    def test_post_batch(self) -> None:
        r = self.client.post("/api/v1/batch", json={})
        self.assertNotEqual(404, r.status_code)

    def test_post_pipeline(self) -> None:
        r = self.client.post("/api/v1/pipeline", json={})
        self.assertNotEqual(404, r.status_code)

    def test_get_health_detailed(self) -> None:
        r = self.client.get("/api/v1/health/detailed")
        self.assertNotEqual(404, r.status_code)

    def test_post_smart_v2(self) -> None:
        r = self.client.post("/api/v1/smart/v2", json={})
        self.assertNotEqual(404, r.status_code)

    def test_get_tasks(self) -> None:
        r = self.client.get("/api/v1/tasks")
        self.assertNotEqual(404, r.status_code)

    def test_get_task_by_id(self) -> None:
        r = self.client.get("/api/v1/tasks/nonexistent-id")
        self.assertNotEqual(404, r.status_code)

    def test_post_task_retry(self) -> None:
        r = self.client.post("/api/v1/tasks/nonexistent-id/retry")
        self.assertNotEqual(404, r.status_code)
