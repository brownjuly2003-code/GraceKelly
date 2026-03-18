from __future__ import annotations

from datetime import UTC, datetime
import unittest
from unittest.mock import AsyncMock, patch

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
                openai_api_key=None,
                openai_base_url="https://api.openai.com/v1",
                openai_timeout_seconds=1.0,
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
                openai_api_key=None,
                openai_base_url="https://api.openai.com/v1",
                openai_timeout_seconds=1.0,
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

    def test_health_routes_offload_blocking_work_to_thread(self) -> None:
        async def run_sync(func, /, *args, **kwargs):
            return func(*args, **kwargs)

        mocked = AsyncMock(side_effect=run_sync)
        with patch("gracekelly.api.routes.health.asyncio.to_thread", new=mocked):
            health = self.client.get("/health")
            readiness = self.client.get("/api/v1/readiness")
            metrics = self.client.get("/metrics")

        self.assertEqual(health.status_code, 200)
        self.assertEqual(readiness.status_code, 200)
        self.assertEqual(metrics.status_code, 200)
        self.assertEqual(mocked.await_count, 3)

    def test_metrics_endpoint_exposes_readiness_execution_and_storage_gauges(self) -> None:
        response = self.client.get("/metrics")

        self.assertEqual(response.status_code, 200)
        self.assertIn("text/plain", response.headers["content-type"])
        self.assertIn('gracekelly_build_info{', response.text)
        self.assertIn('gracekelly_readiness_state{status="ok"} 1', response.text)
        self.assertIn("gracekelly_execution_active_model_executions 0", response.text)
        self.assertIn('gracekelly_execution_model_limit{model_id="mistral-small"} 4', response.text)
        self.assertIn("gracekelly_storage_task_count 0", response.text)
        self.assertIn(
            'gracekelly_browser_circuit_breaker_state{adapter_name="browser.perplexity",state="closed"} 1',
            response.text,
        )

    def test_readiness_exposes_browser_circuit_breaker_details(self) -> None:
        app = create_app(
            Settings(
                env="test",
                host="127.0.0.1",
                port=8011,
                log_level="INFO",
                storage_backend="memory",
                execution_profile="hybrid",
                browser_enabled=True,
                browser_profile_dir=r"D:\GraceKelly\tmp\browser-recon\perplexity-profile",
                browser_base_url="https://www.perplexity.ai",
            )
        )

        class OpenBreakerAdapter:
            name = "browser.perplexity"

            def healthcheck(self) -> dict[str, object]:
                return {
                    "status": "degraded",
                    "adapter_name": self.name,
                    "circuit_breaker": {
                        "enabled": True,
                        "state": "open",
                        "failure_threshold": 3,
                        "cooldown_seconds": 60,
                    },
                }

        app.state.browser_adapter = OpenBreakerAdapter()
        app.state.adapter_registry["browser.perplexity"] = app.state.browser_adapter

        with TestClient(app) as client:
            readiness = client.get("/api/v1/readiness")

        self.assertEqual(readiness.status_code, 200)
        browser = next(
            item for item in readiness.json()["components"] if item["name"] == "browser.perplexity"
        )
        self.assertEqual(browser["status"], "degraded")
        self.assertEqual(browser["details"]["circuit_breaker"]["state"], "open")

    def test_metrics_exposes_open_browser_circuit_breaker(self) -> None:
        app = create_app(
            Settings(
                env="test",
                host="127.0.0.1",
                port=8011,
                log_level="INFO",
                storage_backend="memory",
                execution_profile="hybrid",
                browser_enabled=True,
                browser_profile_dir=r"D:\GraceKelly\tmp\browser-recon\perplexity-profile",
                browser_base_url="https://www.perplexity.ai",
            )
        )

        class OpenBreakerAdapter:
            name = "browser.perplexity"

            def healthcheck(self) -> dict[str, object]:
                return {
                    "status": "degraded",
                    "adapter_name": self.name,
                    "circuit_breaker": {
                        "enabled": True,
                        "state": "open",
                        "failure_threshold": 3,
                        "cooldown_seconds": 60,
                        "consecutive_failures": 3,
                        "open_count": 1,
                        "fail_fast_rejections": 2,
                    },
                }

        app.state.browser_adapter = OpenBreakerAdapter()
        app.state.adapter_registry["browser.perplexity"] = app.state.browser_adapter

        with TestClient(app) as client:
            metrics = client.get("/metrics")

        self.assertEqual(metrics.status_code, 200)
        self.assertIn(
            'gracekelly_browser_circuit_breaker_state{adapter_name="browser.perplexity",state="open"} 1',
            metrics.text,
        )
        self.assertIn(
            'gracekelly_browser_circuit_breaker_consecutive_failures{adapter_name="browser.perplexity"} 3',
            metrics.text,
        )
        self.assertIn(
            'gracekelly_browser_circuit_breaker_fail_fast_rejections{adapter_name="browser.perplexity"} 2',
            metrics.text,
        )

    def test_metrics_can_expose_postgres_storage_counts(self) -> None:
        class FakePostgresRepository(InMemoryTaskRepository):
            backend_name = "postgres"

            def healthcheck(self) -> dict[str, object]:
                return {
                    "status": "ok",
                    "backend": self.backend_name,
                    "schema_version": "0001_initial",
                    "task_count": 7,
                    "step_count": 9,
                    "event_count": 11,
                }

            def schema_report(self) -> dict[str, object]:
                return {
                    "status": "ok",
                    "backend": self.backend_name,
                    "schema_version": "0001_initial",
                }

        client = self._build_client_with_repository(FakePostgresRepository())

        response = client.get("/metrics")

        self.assertEqual(response.status_code, 200)
        self.assertIn("gracekelly_storage_task_count 7", response.text)
        self.assertIn("gracekelly_storage_step_count 9", response.text)
        self.assertIn("gracekelly_storage_event_count 11", response.text)

    def test_readiness_logs_when_overall_status_is_degraded(self) -> None:
        app = create_app(
            Settings(
                env="test",
                host="127.0.0.1",
                port=8011,
                log_level="INFO",
                storage_backend="memory",
                execution_profile="hybrid",
                browser_enabled=True,
                browser_profile_dir=r"D:\GraceKelly\tmp\browser-recon\perplexity-profile",
                browser_base_url="https://www.perplexity.ai",
            )
        )

        class OpenBreakerAdapter:
            name = "browser.perplexity"

            def healthcheck(self) -> dict[str, object]:
                return {
                    "status": "degraded",
                    "adapter_name": self.name,
                    "circuit_breaker": {
                        "enabled": True,
                        "state": "open",
                        "failure_threshold": 3,
                        "cooldown_seconds": 60,
                    },
                }

        app.state.browser_adapter = OpenBreakerAdapter()
        app.state.adapter_registry["browser.perplexity"] = app.state.browser_adapter

        with self.assertLogs("gracekelly.api.routes.health", level="WARNING") as captured:
            with TestClient(app) as client:
                readiness = client.get("/api/v1/readiness")

        self.assertEqual(readiness.status_code, 200)
        self.assertEqual(len(captured.output), 1)
        self.assertIn("readiness.snapshot", captured.output[0])
        self.assertIn('status="degraded"', captured.output[0])

    def test_models_endpoint_returns_aliases_and_reasoning_capability(self) -> None:
        response = self.client.get("/api/v1/models")

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertGreaterEqual(len(payload), 3)
        kimi = next(item for item in payload if item["id"] == "kimi-k2-5")
        mistral = next(item for item in payload if item["id"] == "mistral-small")
        gpt_api = next(item for item in payload if item["id"] == "gpt-5-4-api")
        self.assertIn("Kimi K2", kimi["aliases"])
        self.assertEqual(kimi["adapter_kind"], "browser")
        self.assertEqual(kimi["provider"], "perplexity")
        self.assertTrue(kimi["reasoning_capable"])
        self.assertEqual(kimi["timeout_seconds"], 60)
        self.assertEqual(kimi["expected_latency_class"], "slow")
        self.assertEqual(kimi["concurrency_limit"], 1)
        self.assertIsNone(kimi["available"])
        self.assertEqual(kimi["availability_status"], "unknown")
        self.assertIsNone(kimi["availability_checked_at"])
        self.assertIsNone(kimi["availability_source"])
        self.assertIsNone(kimi["last_verified_at"])
        self.assertEqual(mistral["adapter_kind"], "api")
        self.assertEqual(mistral["provider"], "mistral")
        self.assertFalse(mistral["reasoning_capable"])
        self.assertEqual(mistral["timeout_seconds"], 30)
        self.assertEqual(mistral["expected_latency_class"], "medium")
        self.assertEqual(mistral["concurrency_limit"], 4)
        self.assertIsNone(mistral["available"])
        self.assertEqual(mistral["availability_status"], "static")
        self.assertIsNone(mistral["last_verified_at"])
        self.assertTrue(gpt_api["reasoning_capable"])
        self.assertEqual(gpt_api["timeout_seconds"], 60)
        self.assertEqual(gpt_api["expected_latency_class"], "slow")
        self.assertEqual(gpt_api["concurrency_limit"], 4)
        self.assertEqual(gpt_api["provider"], "openai")
        self.assertEqual(gpt_api["availability_status"], "static")
        self.assertIsNone(gpt_api["last_verified_at"])

    def test_models_endpoint_annotates_browser_availability_from_observed_menu(self) -> None:
        app = create_app(
            Settings(
                env="test",
                host="127.0.0.1",
                port=8011,
                log_level="INFO",
                storage_backend="memory",
                browser_enabled=True,
                browser_profile_dir=r"D:\GraceKelly\tmp\browser-recon\perplexity-profile",
                browser_base_url="https://www.perplexity.ai",
            )
        )

        class ObservedMenuAutomation:
            def healthcheck(self) -> dict[str, object]:
                return {
                    "status": "ok",
                    "implemented": True,
                    "driver": "observed-menu-test",
                    "observed_model_menu": ["Kimi K2", "GPT-5.4", "Best"],
                    "observed_model_menu_at": datetime(2026, 3, 17, 18, 45, tzinfo=UTC),
                    "observed_model_menu_source": "perplexity-model-menu",
                    "verified_model_labels_at": {
                        "GPT-5.4": datetime(2026, 3, 17, 18, 46, tzinfo=UTC),
                    },
                    "last_model_picker_unavailable_at": None,
                }

        app.state.browser_adapter._automation = ObservedMenuAutomation()
        with TestClient(app) as client:
            response = client.get("/api/v1/models")

            self.assertEqual(response.status_code, 200)
            payload = response.json()
            kimi = next(item for item in payload if item["id"] == "kimi-k2-5")
            gpt = next(item for item in payload if item["id"] == "gpt-5-4")
            claude = next(item for item in payload if item["id"] == "claude-sonnet-4-6")
            mistral = next(item for item in payload if item["id"] == "mistral-small")
            self.assertEqual(kimi["availability_status"], "observed_unverified")
            self.assertEqual(kimi["available"], True)
            self.assertEqual(kimi["availability_source"], "perplexity-model-menu")
            self.assertEqual(kimi["availability_checked_at"], "2026-03-17T18:45:00Z")
            self.assertIsNone(kimi["last_verified_at"])
            self.assertEqual(gpt["availability_status"], "observed_available")
            self.assertEqual(gpt["available"], True)
            self.assertEqual(gpt["last_verified_at"], "2026-03-17T18:46:00Z")
            self.assertEqual(claude["availability_status"], "observed_unavailable")
            self.assertEqual(claude["available"], False)
            self.assertIsNone(claude["last_verified_at"])
            self.assertEqual(mistral["availability_status"], "static")
            self.assertIsNone(mistral["available"])

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
        self.assertEqual(task_payload["quorum"], 1)
        self.assertEqual(task_payload["merge_strategy"], "first_success")
        self.assertEqual(task_payload["adapter_hint"], "auto")
        self.assertTrue(task_payload["cancel_on_quorum"])
        self.assertEqual(task_payload["steps"], [])

    def test_orchestrate_route_logs_request_and_acceptance_summary(self) -> None:
        with self.assertLogs("gracekelly.api.routes.orchestrate", level="INFO") as captured:
            response = self.client.post(
                "/api/v1/orchestrate",
                json={
                    "prompt": "route logging",
                    "model": "Kimi K2",
                    "dry_run": True,
                    "metadata": {"trace_id": "route-trace-1"},
                },
            )

        self.assertEqual(response.status_code, 202)
        self.assertEqual(len(captured.output), 2)
        self.assertIn("orchestrate.request", captured.output[0])
        self.assertIn("dry_run=true", captured.output[0])
        self.assertIn("model_count=1", captured.output[0])
        self.assertIn('trace_id="route-trace-1"', captured.output[0])
        self.assertIn("orchestrate.accepted", captured.output[1])
        self.assertIn('status="completed"', captured.output[1])
        self.assertIn('trace_id="route-trace-1"', captured.output[1])

    def test_orchestration_routes_offload_blocking_work_to_thread(self) -> None:
        async def run_sync(func, /, *args, **kwargs):
            return func(*args, **kwargs)

        mocked = AsyncMock(side_effect=run_sync)
        with patch("gracekelly.api.routes.orchestrate.asyncio.to_thread", new=mocked):
            submit = self.client.post(
                "/api/v1/orchestrate",
                json={
                    "prompt": "thread offload",
                    "model": "Kimi K2",
                    "dry_run": True,
                },
            )
            task_id = submit.json()["task_id"]
            recent = self.client.get("/api/v1/tasks", params={"limit": 1})
            task = self.client.get(f"/api/v1/tasks/{task_id}")

        self.assertEqual(submit.status_code, 202)
        self.assertEqual(recent.status_code, 200)
        self.assertEqual(task.status_code, 200)
        self.assertEqual(mocked.await_count, 3)

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
        self.assertIsNone(payload[0]["model"])
        self.assertEqual(payload[0]["dry_run"], True)
        self.assertEqual(payload[0]["model_count"], 1)
        self.assertEqual(payload[0]["requested_models"][0]["id"], "mistral-small")
        self.assertEqual(payload[0]["cancelled_step_count"], 0)
        self.assertIsNone(payload[0]["cancel_reason"])
        self.assertNotIn("steps", payload[0])
        self.assertNotIn("events", payload[0])

    def test_task_routes_log_list_and_not_found_events(self) -> None:
        self.client.post(
            "/api/v1/orchestrate",
            json={
                "prompt": "log list task",
                "model": "Kimi K2",
                "dry_run": True,
            },
        )

        with self.assertLogs("gracekelly.api.routes.orchestrate", level="INFO") as captured:
            response = self.client.get("/api/v1/tasks", params={"limit": 5, "dry_run": "true"})

        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(captured.output), 1)
        self.assertIn("tasks.list", captured.output[0])
        self.assertIn("result_count=1", captured.output[0])

        with self.assertLogs("gracekelly.api.routes.orchestrate", level="WARNING") as captured:
            response = self.client.get("/api/v1/tasks/task-does-not-exist")

        self.assertEqual(response.status_code, 404)
        self.assertEqual(len(captured.output), 1)
        self.assertIn("task.get.not_found", captured.output[0])

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
                "execution_mode": "api",
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
        self.assertIsNone(payload[0]["model"])
        self.assertEqual(payload[0]["dry_run"], False)
        self.assertEqual(payload[0]["failure_code"], "provider_unavailable")
        self.assertEqual(payload[0]["requested_models"][0]["id"], "mistral-small")
        self.assertEqual(payload[0]["cancelled_step_count"], 0)
        self.assertIsNone(payload[0]["cancel_reason"])
        self.assertEqual(payload[0]["execution_mode"], "api")

    def test_list_tasks_exposes_winning_model_and_short_circuit_summary(self) -> None:
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
                browser_scripted_output_text="browser wins",
            )
        )
        client = TestClient(app)

        response = client.post(
            "/api/v1/orchestrate",
            json={
                "prompt": "short circuit summary",
                "models": ["Kimi K2", "Mistral"],
                "dry_run": False,
                "quorum": 1,
                "merge_strategy": "first_success",
                "cancel_on_quorum": True,
            },
        )

        self.assertEqual(response.status_code, 202)

        recent = client.get("/api/v1/tasks", params={"limit": 1})

        self.assertEqual(recent.status_code, 200)
        payload = recent.json()
        self.assertEqual(len(payload), 1)
        self.assertEqual(payload[0]["task_id"], response.json()["task_id"])
        self.assertEqual(payload[0]["adapter_name"], "browser.perplexity")
        self.assertEqual(payload[0]["model"]["id"], "kimi-k2-5")
        self.assertEqual(payload[0]["cancelled_step_count"], 1)
        self.assertEqual(payload[0]["cancel_reason"], "quorum_reached")
        self.assertEqual(payload[0]["execution_mode"], "mixed")

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
            def list_recent(self, limit: int, **kwargs):
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
        self.assertEqual(task_payload["quorum"], 1)
        self.assertEqual(task_payload["merge_strategy"], "first_success")
        self.assertEqual(task_payload["adapter_hint"], "auto")
        self.assertTrue(task_payload["cancel_on_quorum"])
        self.assertEqual(task_payload["winning_step_index"], 1)
        self.assertEqual(task_payload["cancelled_steps"], [])
        self.assertIsNone(task_payload["cancel_reason"])
        self.assertEqual(task_payload["execution_details"]["adapter_names"], ["browser.perplexity"])
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
        self.assertEqual(task_payload["quorum"], 1)
        self.assertEqual(task_payload["merge_strategy"], "first_success")
        self.assertEqual(task_payload["adapter_hint"], "auto")
        self.assertTrue(task_payload["cancel_on_quorum"])
        self.assertIsNone(task_payload["winning_step_index"])
        self.assertEqual(task_payload["cancelled_steps"], [])
        self.assertIsNone(task_payload["cancel_reason"])
        self.assertEqual(task_payload["execution_details"]["failure_codes"], ["auth_failed"])
        self.assertEqual(task_payload["events"][1]["payload"]["details"]["provider"], "perplexity")
        self.assertTrue(task_payload["events"][1]["payload"]["details"]["configured"])
        self.assertEqual(task_payload["events"][2]["payload"]["details"]["failure_codes"], ["auth_failed"])
        self.assertEqual(task_payload["events"][2]["payload"]["details"]["failed_step_count"], 1)


if __name__ == "__main__":
    unittest.main()
