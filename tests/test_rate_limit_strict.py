from __future__ import annotations

import unittest

from fastapi.testclient import TestClient

from gracekelly.config import Settings
from gracekelly.main import create_app


def _settings_no_key(require_auth: bool) -> Settings:
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
        api_key=None,
        require_auth=require_auth,
    )


class RequireAuthTests(unittest.TestCase):
    def test_strict_mode_blocks_protected_endpoint(self) -> None:
        client = TestClient(create_app(_settings_no_key(require_auth=True)))
        resp = client.post("/api/v1/orchestrate", json={"prompt": "hi", "model": "Kimi K2"})
        self.assertEqual(resp.status_code, 503)

    def test_strict_mode_allows_health(self) -> None:
        client = TestClient(create_app(_settings_no_key(require_auth=True)))
        resp = client.get("/health")
        self.assertEqual(resp.status_code, 200)

    def test_non_strict_mode_allows_without_key(self) -> None:
        client = TestClient(create_app(_settings_no_key(require_auth=False)))
        resp = client.get("/health")
        self.assertEqual(resp.status_code, 200)

    def test_require_auth_default_is_false(self) -> None:
        s = _settings_no_key(require_auth=False)
        self.assertFalse(s.require_auth)


if __name__ == "__main__":
    unittest.main()
