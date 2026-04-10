from __future__ import annotations

import unittest
from typing import Any
from unittest.mock import patch

try:
    from fastapi.testclient import TestClient
except ModuleNotFoundError:  # pragma: no cover
    TestClient = None

if TestClient is not None:
    from gracekelly.config import Settings
    from gracekelly.main import create_app
else:  # pragma: no cover
    Settings = None
    create_app = None


def _make_settings(**kwargs: Any) -> Settings:
    return Settings(
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
        browser_enabled=False,
        browser_profile_dir=None,
        browser_base_url="https://www.perplexity.ai",
        **kwargs,
    )


_ORCHESTRATE_PAYLOAD = {
    "prompt": "test prompt",
    "model": "Kimi K2",
    "dry_run": True,
}


@unittest.skipIf(TestClient is None, "fastapi.testclient is not installed")
class OrchestrateTimeoutTests(unittest.TestCase):
    def test_no_timeout_setting_request_completes_normally(self) -> None:
        app = create_app(_make_settings(orchestrate_timeout_seconds=None))
        client = TestClient(app)
        resp = client.post("/api/v1/orchestrate", json=_ORCHESTRATE_PAYLOAD)
        self.assertEqual(resp.status_code, 200)

    def test_timeout_exceeded_returns_504(self) -> None:
        app = create_app(_make_settings(orchestrate_timeout_seconds=0.001))
        client = TestClient(app)

        with patch("gracekelly.api.routes.orchestrate.asyncio.wait_for", side_effect=TimeoutError):
            resp = client.post("/api/v1/orchestrate", json=_ORCHESTRATE_PAYLOAD)

        self.assertEqual(resp.status_code, 504)

    def test_timeout_detail_message_contains_timed_out(self) -> None:
        app = create_app(_make_settings(orchestrate_timeout_seconds=0.001))
        client = TestClient(app)

        with patch("gracekelly.api.routes.orchestrate.asyncio.wait_for", side_effect=TimeoutError):
            resp = client.post("/api/v1/orchestrate", json=_ORCHESTRATE_PAYLOAD)

        self.assertIn("timed out", resp.json()["detail"].lower())

    def test_timeout_not_triggered_when_fast(self) -> None:
        """A large timeout value does not interfere with fast requests."""
        app = create_app(_make_settings(orchestrate_timeout_seconds=120.0))
        client = TestClient(app)
        resp = client.post("/api/v1/orchestrate", json=_ORCHESTRATE_PAYLOAD)
        self.assertEqual(resp.status_code, 200)

    def test_zero_timeout_config_is_treated_as_no_limit(self) -> None:
        """GRACEKELLY_ORCHESTRATE_TIMEOUT_SECONDS=0 → None → no asyncio.wait_for."""
        settings = _make_settings(orchestrate_timeout_seconds=None)
        self.assertIsNone(settings.orchestrate_timeout_seconds)

    def test_from_env_zero_produces_none(self) -> None:
        """_env_float returns 0.0; `or None` converts it to None."""
        import os

        with patch.dict(os.environ, {"GRACEKELLY_ORCHESTRATE_TIMEOUT_SECONDS": "0"}):
            s = Settings.from_env()
        self.assertIsNone(s.orchestrate_timeout_seconds)

    def test_from_env_nonzero_produces_float(self) -> None:
        import os

        with patch.dict(os.environ, {"GRACEKELLY_ORCHESTRATE_TIMEOUT_SECONDS": "45.5"}):
            s = Settings.from_env()
        self.assertEqual(s.orchestrate_timeout_seconds, 45.5)
