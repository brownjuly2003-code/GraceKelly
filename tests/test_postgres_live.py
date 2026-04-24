from __future__ import annotations

import os
import unittest

try:
    from fastapi.testclient import TestClient
except ModuleNotFoundError:  # pragma: no cover
    TestClient = None  # type: ignore[assignment,misc]

if TestClient is not None:
    from gracekelly.config import Settings
    from gracekelly.main import create_app
    from gracekelly.storage.postgres import psycopg  # type: ignore[attr-defined]
else:  # pragma: no cover
    Settings = None  # type: ignore[misc]
    create_app = None
    psycopg = None


POSTGRES_TEST_DSN = os.getenv("GRACEKELLY_POSTGRES_TEST_DSN")


@unittest.skipUnless(TestClient is not None, "fastapi.testclient is not installed")
@unittest.skipUnless(psycopg is not None, "psycopg is not installed")
@unittest.skipUnless(
    POSTGRES_TEST_DSN,
    "GRACEKELLY_POSTGRES_TEST_DSN is required for live PostgreSQL integration tests",
)
class PostgresLiveIntegrationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.client = TestClient(
            create_app(
                Settings(
                    env="test",
                    host="127.0.0.1",
                    port=8011,
                    log_level="INFO",
                    storage_backend="postgres",
                    postgres_dsn=POSTGRES_TEST_DSN,
                    execution_profile="dry-run",
                    mistral_api_key=None,
                    mistral_base_url="https://api.mistral.ai/v1",
                    mistral_timeout_seconds=1.0,
                    browser_enabled=False,
                    browser_profile_dir=None,
                    browser_base_url="https://www.perplexity.ai",
                )
            )
        )

    def test_dry_run_roundtrip_persists_task_and_event(self) -> None:
        response = self.client.post(
            "/api/v1/orchestrate",
            json={
                "prompt": "postgres dry run",
                "models": ["Kimi K2", "GPT-5.4 API"],
                "dry_run": True,
            },
        )

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["status"], "completed")
        self.assertEqual(len(payload["requested_models"]), 2)
        self.assertNotIn("steps", payload)

        task = self.client.get(f"/api/v1/tasks/{payload['task_id']}")
        self.assertEqual(task.status_code, 200)
        task_payload = task.json()
        self.assertEqual([event["event_type"] for event in task_payload["events"]], ["task.accepted"])
        self.assertEqual(task_payload["steps"], [])

    def test_provider_failure_roundtrip_persists_step_and_events(self) -> None:
        response = self.client.post(
            "/api/v1/orchestrate",
            json={
                "prompt": "postgres provider failure",
                "model": "GPT-5.4 API",
                "dry_run": False,
            },
        )

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["status"], "failed")
        self.assertEqual(payload["failure_code"], "provider_unavailable")
        self.assertEqual(len(payload["requested_models"]), 1)
        self.assertNotIn("steps", payload)

        task = self.client.get(f"/api/v1/tasks/{payload['task_id']}")
        self.assertEqual(task.status_code, 200)
        task_payload = task.json()
        self.assertEqual(
            [event["event_type"] for event in task_payload["events"]],
            ["task.accepted", "step.failed", "task.failed"],
        )
        self.assertEqual(task_payload["steps"][0]["failure_code"], "provider_unavailable")

    def test_recent_task_summaries_and_filters_work_on_postgres_backend(self) -> None:
        dry_run = self.client.post(
            "/api/v1/orchestrate",
            json={
                "prompt": "postgres list dry run",
                "model": "Kimi K2",
                "dry_run": True,
            },
        )
        failed = self.client.post(
            "/api/v1/orchestrate",
            json={
                "prompt": "postgres list failed",
                "model": "GPT-5.4 API",
                "dry_run": False,
            },
        )

        self.assertEqual(dry_run.status_code, 200)
        self.assertEqual(failed.status_code, 200)

        recent = self.client.get("/api/v1/tasks", params={"limit": 2})
        self.assertEqual(recent.status_code, 200)
        recent_payload = recent.json()
        self.assertGreaterEqual(len(recent_payload), 2)
        recent_ids = [item["task_id"] for item in recent_payload]
        self.assertIn(dry_run.json()["task_id"], recent_ids)
        self.assertIn(failed.json()["task_id"], recent_ids)

        filtered = self.client.get(
            "/api/v1/tasks",
            params={
                "status": "failed",
                "execution_mode": "api",
                "dry_run": "false",
                "failure_code": "provider_unavailable",
            },
        )
        self.assertEqual(filtered.status_code, 200)
        filtered_payload = filtered.json()
        self.assertGreaterEqual(len(filtered_payload), 1)
        self.assertEqual(filtered_payload[0]["task_id"], failed.json()["task_id"])
        self.assertEqual(filtered_payload[0]["adapter_name"], "api.openai")
        self.assertIsNone(filtered_payload[0]["model"])
        self.assertEqual(filtered_payload[0]["failure_code"], "provider_unavailable")
        self.assertEqual(filtered_payload[0]["requested_models"][0]["id"], "gpt-5-4-api")
        self.assertEqual(filtered_payload[0]["cancelled_step_count"], 0)
        self.assertEqual(filtered_payload[0]["execution_mode"], "api")


if __name__ == "__main__":
    unittest.main()
