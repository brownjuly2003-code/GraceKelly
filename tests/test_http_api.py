from __future__ import annotations

import unittest

try:
    from fastapi.testclient import TestClient
except ModuleNotFoundError:  # pragma: no cover
    TestClient = None

if TestClient is not None:
    from gracekelly.config import Settings
    from gracekelly.core.orchestrator import OrchestratorService
    from gracekelly.main import create_app
    from gracekelly.storage.memory import InMemoryTaskRepository
else:  # pragma: no cover
    Settings = None
    OrchestratorService = None
    create_app = None
    InMemoryTaskRepository = None


@unittest.skipIf(TestClient is None, "fastapi.testclient is not installed")
class HttpApiSmokeTests(unittest.TestCase):
    def setUp(self) -> None:
        app = create_app(
            Settings(
                env="test",
                host="127.0.0.1",
                port=8011,
                log_level="INFO",
                storage_backend="memory",
                postgres_dsn=None,
                mistral_api_key=None,
                mistral_base_url="https://api.mistral.ai/v1",
                mistral_timeout_seconds=1.0,
                browser_enabled=False,
                browser_profile_dir=None,
                browser_base_url="https://www.perplexity.ai",
            )
        )
        self.client = TestClient(app)

    def _build_client_with_repository(self, repository) -> TestClient:
        app = create_app(
            Settings(
                env="test",
                host="127.0.0.1",
                port=8011,
                log_level="INFO",
                storage_backend="memory",
                postgres_dsn=None,
                mistral_api_key=None,
                mistral_base_url="https://api.mistral.ai/v1",
                mistral_timeout_seconds=1.0,
                browser_enabled=False,
                browser_profile_dir=None,
                browser_base_url="https://www.perplexity.ai",
            )
        )
        app.state.task_repository = repository
        app.state.orchestrator_service = OrchestratorService(
            repository,
            execution_router=app.state.execution_router,
        )
        return TestClient(app)

    def test_health_and_readiness_endpoints(self) -> None:
        health = self.client.get("/health")
        readiness = self.client.get("/api/v1/readiness")

        self.assertEqual(health.status_code, 200)
        self.assertEqual(readiness.status_code, 200)
        self.assertEqual(health.json()["service"], "gracekelly")
        self.assertEqual(readiness.json()["environment"], "test")
        self.assertEqual(health.json()["active_model_executions"], 0)
        self.assertEqual(health.json()["saturated_models"], [])
        self.assertGreaterEqual(len(readiness.json()["components"]), 4)
        storage = next(item for item in readiness.json()["components"] if item["kind"] == "storage")
        execution = next(item for item in readiness.json()["components"] if item["kind"] == "execution")
        self.assertEqual(storage["details"]["schema"]["schema_version"], "not_applicable")
        self.assertEqual(execution["details"]["active_model_executions"], 0)
        self.assertEqual(execution["details"]["model_limits"]["mistral-small"], 4)

    def test_models_endpoint_returns_aliases_and_reasoning_capability(self) -> None:
        response = self.client.get("/api/v1/models")

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertGreaterEqual(len(payload), 2)
        kimi = next(item for item in payload if item["id"] == "kimi-k2-5")
        mistral = next(item for item in payload if item["id"] == "mistral-small")
        self.assertIn("Kimi K2", kimi["aliases"])
        self.assertTrue(kimi["reasoning_capable"])
        self.assertEqual(kimi["timeout_seconds"], 60)
        self.assertEqual(kimi["expected_latency_class"], "slow")
        self.assertEqual(kimi["concurrency_limit"], 1)
        self.assertFalse(mistral["reasoning_capable"])
        self.assertEqual(mistral["timeout_seconds"], 30)
        self.assertEqual(mistral["expected_latency_class"], "medium")
        self.assertEqual(mistral["concurrency_limit"], 4)

    def test_orchestrate_and_fetch_task_in_dry_run(self) -> None:
        response = self.client.post(
            "/api/v1/orchestrate",
            json={
                "prompt": "dry run prompt",
                "models": ["Kimi K2", "Mistral"],
                "dry_run": True,
                "quorum": 1,
            },
        )

        self.assertEqual(response.status_code, 202)
        payload = response.json()
        self.assertEqual(payload["status"], "completed")
        self.assertEqual(len(payload["requested_models"]), 2)
        self.assertIsNone(payload["model"])
        self.assertNotIn("steps", payload)
        self.assertNotIn("events", payload)

        task = self.client.get(f"/api/v1/tasks/{payload['task_id']}")
        self.assertEqual(task.status_code, 200)
        task_payload = task.json()
        self.assertEqual(len(task_payload["events"]), 1)
        self.assertEqual(task_payload["events"][0]["event_type"], "task.accepted")
        self.assertEqual(task_payload["steps"], [])

    def test_list_tasks_returns_recent_summaries_in_desc_order(self) -> None:
        first = self.client.post(
            "/api/v1/orchestrate",
            json={
                "prompt": "first task",
                "model": "Kimi K2",
                "dry_run": True,
            },
        )
        second = self.client.post(
            "/api/v1/orchestrate",
            json={
                "prompt": "second task",
                "model": "Mistral",
                "dry_run": True,
            },
        )

        self.assertEqual(first.status_code, 202)
        self.assertEqual(second.status_code, 202)

        response = self.client.get("/api/v1/tasks", params={"limit": 1})

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(len(payload), 1)
        self.assertEqual(payload[0]["task_id"], second.json()["task_id"])
        self.assertEqual(payload[0]["adapter_name"], "dry-run")
        self.assertEqual(payload[0]["dry_run"], True)
        self.assertEqual(payload[0]["model_count"], 1)
        self.assertEqual(payload[0]["requested_models"][0]["id"], "mistral-small")
        self.assertNotIn("steps", payload[0])
        self.assertNotIn("events", payload[0])

    def test_list_tasks_can_filter_by_status_and_dry_run(self) -> None:
        self.client.post(
            "/api/v1/orchestrate",
            json={
                "prompt": "dry run completed",
                "model": "Kimi K2",
                "dry_run": True,
            },
        )
        failed = self.client.post(
            "/api/v1/orchestrate",
            json={
                "prompt": "real failure",
                "model": "Mistral",
                "dry_run": False,
            },
        )

        response = self.client.get(
            "/api/v1/tasks",
            params={
                "status": "failed",
                "dry_run": "false",
                "failure_code": "provider_unavailable",
            },
        )

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(len(payload), 1)
        self.assertEqual(payload[0]["task_id"], failed.json()["task_id"])
        self.assertEqual(payload[0]["adapter_name"], "api.mistral")
        self.assertEqual(payload[0]["status"], "failed")
        self.assertEqual(payload[0]["dry_run"], False)
        self.assertEqual(payload[0]["failure_code"], "provider_unavailable")
        self.assertEqual(payload[0]["requested_models"][0]["id"], "mistral-small")

    def test_api_execution_without_key_fails_cleanly(self) -> None:
        response = self.client.post(
            "/api/v1/orchestrate",
            json={
                "prompt": "mistral without key",
                "model": "Mistral",
                "dry_run": False,
            },
        )

        self.assertEqual(response.status_code, 202)
        payload = response.json()
        self.assertEqual(payload["status"], "failed")
        self.assertEqual(payload["adapter_name"], "api.mistral")
        self.assertEqual(payload["failure_code"], "provider_unavailable")
        self.assertEqual(payload["model"], None)
        self.assertNotIn("steps", payload)

    def test_orchestrate_rejects_unknown_merge_strategy(self) -> None:
        response = self.client.post(
            "/api/v1/orchestrate",
            json={
                "prompt": "bad strategy",
                "model": "Mistral",
                "merge_strategy": "fanout",
            },
        )

        self.assertEqual(response.status_code, 422)

    def test_orchestrate_returns_storage_failed_when_task_persistence_breaks(self) -> None:
        class SaveFailingRepository(InMemoryTaskRepository):
            def save_task_with_steps(self, task, steps) -> None:
                raise RuntimeError("database is offline")

        client = self._build_client_with_repository(SaveFailingRepository())

        response = client.post(
            "/api/v1/orchestrate",
            json={
                "prompt": "storage failure",
                "model": "Kimi K2",
                "dry_run": True,
            },
        )

        self.assertEqual(response.status_code, 503)
        payload = response.json()
        self.assertEqual(payload["detail"]["code"], "storage_failed")
        self.assertIn("save_task_with_steps", payload["detail"]["message"])

    def test_get_task_returns_storage_failed_when_repository_read_breaks(self) -> None:
        class ReadFailingRepository(InMemoryTaskRepository):
            def get(self, task_id: str):
                raise RuntimeError("database is offline")

        client = self._build_client_with_repository(ReadFailingRepository())

        response = client.get("/api/v1/tasks/task-123")

        self.assertEqual(response.status_code, 503)
        payload = response.json()
        self.assertEqual(payload["detail"]["code"], "storage_failed")
        self.assertIn("get_task", payload["detail"]["message"])

    def test_list_tasks_returns_storage_failed_when_repository_read_breaks(self) -> None:
        class ListFailingRepository(InMemoryTaskRepository):
            def list_recent(self, limit: int):
                raise RuntimeError("database is offline")

        client = self._build_client_with_repository(ListFailingRepository())

        response = client.get("/api/v1/tasks")

        self.assertEqual(response.status_code, 503)
        payload = response.json()
        self.assertEqual(payload["detail"]["code"], "storage_failed")
        self.assertIn("list_recent_tasks", payload["detail"]["message"])

    def test_orchestrate_preserves_requested_models_when_event_persistence_fails(self) -> None:
        class EventFailingRepository(InMemoryTaskRepository):
            def append_event(self, event) -> None:
                raise RuntimeError("event sink offline")

        client = self._build_client_with_repository(EventFailingRepository())

        response = client.post(
            "/api/v1/orchestrate",
            json={
                "prompt": "dry run with event failure",
                "models": ["Kimi K2", "Mistral"],
                "dry_run": True,
            },
        )

        self.assertEqual(response.status_code, 202)
        payload = response.json()
        self.assertEqual([item["id"] for item in payload["requested_models"]], ["kimi-k2-5", "mistral-small"])

    def test_orchestrate_summary_does_not_depend_on_post_write_readback(self) -> None:
        class ReadbackFailingRepository(InMemoryTaskRepository):
            def list_steps(self, task_id: str):
                raise RuntimeError("read path offline")

            def list_events(self, task_id: str):
                raise RuntimeError("read path offline")

        client = self._build_client_with_repository(ReadbackFailingRepository())

        response = client.post(
            "/api/v1/orchestrate",
            json={
                "prompt": "summary without readback",
                "model": "Kimi K2",
                "dry_run": True,
            },
        )

        self.assertEqual(response.status_code, 202)
        payload = response.json()
        self.assertEqual(payload["status"], "completed")
        self.assertEqual(payload["adapter_name"], "dry-run")
        self.assertEqual(payload["requested_models"][0]["id"], "kimi-k2-5")

    def test_orchestrate_rejects_duplicate_canonical_models(self) -> None:
        response = self.client.post(
            "/api/v1/orchestrate",
            json={
                "prompt": "duplicate canonical model",
                "models": ["Kimi K2", "Kimi K2.5"],
                "dry_run": True,
            },
        )

        self.assertEqual(response.status_code, 422)
        self.assertIn("Duplicate model request after canonicalization", response.json()["detail"])

    def test_orchestrate_rejects_concat_with_short_circuiting_quorum(self) -> None:
        response = self.client.post(
            "/api/v1/orchestrate",
            json={
                "prompt": "truncated concat",
                "models": ["Kimi K2", "Mistral"],
                "dry_run": False,
                "merge_strategy": "concat",
                "quorum": 1,
                "cancel_on_quorum": True,
            },
        )

        self.assertEqual(response.status_code, 422)
        self.assertIn("merge_strategy='concat'", response.json()["detail"])

    def test_orchestrate_rejects_reasoning_for_unsupported_model(self) -> None:
        response = self.client.post(
            "/api/v1/orchestrate",
            json={
                "prompt": "reasoning on unsupported model",
                "model": "Mistral",
                "reasoning": True,
            },
        )

        self.assertEqual(response.status_code, 422)
        self.assertIn("reasoning=true is not supported", response.json()["detail"])

    def test_browser_execution_can_run_through_scripted_backend(self) -> None:
        app = create_app(
            Settings(
                env="test",
                host="127.0.0.1",
                port=8011,
                log_level="INFO",
                storage_backend="memory",
                postgres_dsn=None,
                execution_profile="hybrid",
                mistral_api_key=None,
                mistral_base_url="https://api.mistral.ai/v1",
                mistral_timeout_seconds=1.0,
                browser_enabled=True,
                browser_automation_backend="scripted",
                browser_profile_dir="D:\\Profiles\\GraceKelly",
                browser_base_url="https://www.perplexity.ai",
                browser_scripted_logged_in=True,
                browser_scripted_model_label="Kimi K2",
                browser_scripted_output_text="scripted browser success",
            )
        )
        client = TestClient(app)

        response = client.post(
            "/api/v1/orchestrate",
            json={
                "prompt": "browser execution",
                "model": "Kimi K2",
                "dry_run": False,
            },
        )

        self.assertEqual(response.status_code, 202)
        payload = response.json()
        self.assertEqual(payload["status"], "completed")
        self.assertEqual(payload["adapter_name"], "browser.perplexity")
        self.assertEqual(payload["output_text"], "scripted browser success")

        task = client.get(f"/api/v1/tasks/{payload['task_id']}")
        self.assertEqual(task.status_code, 200)
        task_payload = task.json()
        self.assertEqual(len(task_payload["steps"]), 1)
        self.assertEqual(task_payload["steps"][0]["backend"], "browser")
        self.assertEqual(
            [event["event_type"] for event in task_payload["events"]],
            ["task.accepted", "step.completed", "task.completed"],
        )
        self.assertEqual(task_payload["events"][1]["payload"]["details"]["driver"], "scripted")
        self.assertEqual(task_payload["events"][2]["payload"]["details"]["adapter_names"], ["browser.perplexity"])
        self.assertEqual(task_payload["events"][2]["payload"]["details"]["completed_step_count"], 1)

    def test_browser_execution_reports_auth_failure_through_scripted_backend(self) -> None:
        app = create_app(
            Settings(
                env="test",
                host="127.0.0.1",
                port=8011,
                log_level="INFO",
                storage_backend="memory",
                postgres_dsn=None,
                execution_profile="hybrid",
                mistral_api_key=None,
                mistral_base_url="https://api.mistral.ai/v1",
                mistral_timeout_seconds=1.0,
                browser_enabled=True,
                browser_automation_backend="scripted",
                browser_profile_dir="D:\\Profiles\\GraceKelly",
                browser_base_url="https://www.perplexity.ai",
                browser_scripted_logged_in=False,
                browser_scripted_model_label="Kimi K2",
                browser_scripted_output_text="unused",
            )
        )
        client = TestClient(app)

        response = client.post(
            "/api/v1/orchestrate",
            json={
                "prompt": "browser auth failure",
                "model": "Kimi K2",
                "dry_run": False,
            },
        )

        self.assertEqual(response.status_code, 202)
        payload = response.json()
        self.assertEqual(payload["status"], "failed")
        self.assertEqual(payload["adapter_name"], "browser.perplexity")
        self.assertEqual(payload["failure_code"], "auth_failed")

        task = client.get(f"/api/v1/tasks/{payload['task_id']}")
        self.assertEqual(task.status_code, 200)
        task_payload = task.json()
        self.assertEqual(task_payload["steps"][0]["failure_code"], "auth_failed")
        self.assertEqual(
            [event["event_type"] for event in task_payload["events"]],
            ["task.accepted", "step.failed", "task.failed"],
        )
        self.assertEqual(task_payload["events"][1]["payload"]["details"]["provider"], "perplexity")
        self.assertTrue(task_payload["events"][1]["payload"]["details"]["configured"])
        self.assertEqual(task_payload["events"][2]["payload"]["details"]["failure_codes"], ["auth_failed"])
        self.assertEqual(task_payload["events"][2]["payload"]["details"]["failed_step_count"], 1)


if __name__ == "__main__":
    unittest.main()
