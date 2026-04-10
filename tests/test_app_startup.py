from __future__ import annotations

import unittest

try:
    from fastapi.testclient import TestClient
except ModuleNotFoundError:  # pragma: no cover
    TestClient = None  # type: ignore[assignment,misc]

if TestClient is not None:
    from gracekelly.config import Settings
    from gracekelly.main import create_app
else:  # pragma: no cover
    Settings = None  # type: ignore[misc]
    create_app = None


@unittest.skipIf(TestClient is None, "fastapi.testclient is not installed")
class AppStartupTests(unittest.TestCase):
    def test_default_startup_succeeds(self) -> None:
        app = create_app(Settings(
            env="test",
            host="127.0.0.1",
            port=8011,
            log_level="INFO",
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
        client = TestClient(app)
        health = client.get("/health")
        self.assertEqual(health.status_code, 200)
        self.assertIn("status", health.json())

    def test_app_factory_returns_fresh_instance(self) -> None:
        from gracekelly.main import app_factory
        app1 = app_factory()
        app2 = app_factory()
        self.assertIsNot(app1, app2)


if __name__ == "__main__":
    unittest.main()
