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
    Settings = None  # type: ignore[assignment,misc]
    create_app = None  # type: ignore[assignment]


@unittest.skipIf(TestClient is None, "fastapi.testclient is not installed")
class OrchestrateProfileGateTests(unittest.TestCase):
    def test_orchestrate_uses_dry_run_when_profile_is_dry_run(self) -> None:
        app = create_app(
            Settings(
                env="test",
                host="127.0.0.1",
                port=8011,
                log_level="INFO",
                storage_backend="memory",
                postgres_dsn=None,
                execution_profile="dry-run",
                openai_api_key=None,
                anthropic_api_key=None,
                browser_enabled=False,
                browser_profile_dir=None,
            )
        )
        client = TestClient(app)

        response = client.post(
            "/api/v1/orchestrate",
            json={
                "prompt": "2+2",
                "model": "claude-sonnet-4-6",
                "reliability_level": "quick",
            },
        )

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["status"], "completed")
        self.assertEqual(payload["execution_mode"], "dry-run")
        self.assertEqual(payload["adapter_name"], "dry-run")
        self.assertIn("[dry-run]", payload["output_text"])
