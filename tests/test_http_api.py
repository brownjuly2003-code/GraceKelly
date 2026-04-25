from __future__ import annotations

import json
import sys
import unittest
from collections.abc import Callable, Iterator
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any, cast
from unittest.mock import AsyncMock, patch

try:
    from fastapi.testclient import TestClient
except ModuleNotFoundError:  # pragma: no cover
    HAS_TEST_CLIENT = False
else:
    HAS_TEST_CLIENT = True

if HAS_TEST_CLIENT:
    from gracekelly.config import Settings
    from gracekelly.core.contracts import ExecutionRequest, StreamChunk
    from gracekelly.core.models import build_browser_catalog
    from gracekelly.core.orchestrator import OrchestratorService, StorageUnavailableError
    from gracekelly.main import create_app
    from gracekelly.storage.base import TaskEventRecord, TaskRecord, TaskStepRecord
    from gracekelly.storage.memory import InMemoryTaskRepository

if TYPE_CHECKING:
    from fastapi.testclient import TestClient

    from gracekelly.config import Settings
    from gracekelly.core.contracts import ExecutionRequest, StreamChunk
    from gracekelly.core.models import build_browser_catalog
    from gracekelly.core.orchestrator import OrchestratorService
    from gracekelly.main import create_app
    from gracekelly.storage.base import TaskEventRecord, TaskRecord, TaskStepRecord
    from gracekelly.storage.memory import InMemoryTaskRepository


@unittest.skipIf(not HAS_TEST_CLIENT, "fastapi.testclient is not installed")
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

    def _build_client_with_repository(self, repository: Any) -> TestClient:
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
        self.assertIn("status", health.json())
        self.assertNotIn("saturated_models", health.json())
        self.assertNotIn("active_model_executions", health.json())
        self.assertEqual(readiness.json()["environment"], "test")
        self.assertGreaterEqual(len(readiness.json()["components"]), 4)
        storage = next(item for item in readiness.json()["components"] if item["kind"] == "storage")
        execution = next(item for item in readiness.json()["components"] if item["kind"] == "execution")
        self.assertEqual(storage["details"]["schema"]["schema_version"], "not_applicable")
        self.assertEqual(execution["details"]["active_model_executions"], 0)
        self.assertEqual(execution["details"]["model_limits"]["gpt-5-4-api"], 4)

    def test_health_routes_offload_blocking_work_to_thread(self) -> None:
        async def run_sync(func: Callable[..., Any], /, *args: Any, **kwargs: Any) -> Any:
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
        self.assertIn('gracekelly_execution_model_limit{model_id="gpt-5-4-api"} 4', response.text)
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
        repository = InMemoryTaskRepository()
        repository.save_model_catalog_snapshot(
            build_browser_catalog(
                (
                    "Best",
                    "Sonar",
                    "Claude Opus 4.6",
                    "Max",
                    "Nemotron 3 Super",
                    "Kimi K2.5",
                ),
                checked_at=datetime(2026, 4, 20, 12, 0, tzinfo=UTC),
                source="perplexity-model-menu",
            )
        )
        client = self._build_client_with_repository(repository)
        response = client.get("/api/v1/models")

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        catalog = payload["models"]
        self.assertGreaterEqual(len(catalog), 3)
        best = next(item for item in catalog if item["id"] == "best")
        sonar = next(item for item in catalog if item["id"] == "sonar")
        opus = next(item for item in catalog if item["id"] == "claude-opus-4-6")
        max_model = next(item for item in catalog if item["id"] == "max")
        nemotron = next(item for item in catalog if item["id"] == "nemotron-3-super")
        kimi = next(item for item in catalog if item["id"] == "kimi-k2-5")
        claude_api = next(item for item in catalog if item["id"] == "claude-sonnet-4-6-api")
        gpt_api = next(item for item in catalog if item["id"] == "gpt-5-4-api")
        self.assertEqual(best["adapter_kind"], "browser")
        self.assertEqual(best["availability_status"], "observed_unverified")
        self.assertTrue(best["reasoning_capable"])
        self.assertEqual(sonar["provider"], "perplexity")
        self.assertEqual(opus["display_name"], "Claude Opus 4.6")
        self.assertEqual(max_model["timeout_seconds"], 60)
        self.assertEqual(nemotron["concurrency_limit"], 1)
        self.assertIn("Kimi K2", kimi["aliases"])
        self.assertEqual(kimi["adapter_kind"], "browser")
        self.assertEqual(kimi["provider"], "perplexity")
        self.assertTrue(kimi["reasoning_capable"])
        self.assertEqual(kimi["timeout_seconds"], 60)
        self.assertEqual(kimi["expected_latency_class"], "slow")
        self.assertEqual(kimi["concurrency_limit"], 1)
        self.assertTrue(kimi["available"])
        self.assertEqual(kimi["availability_status"], "observed_unverified")
        self.assertEqual(kimi["availability_checked_at"], "2026-04-20T12:00:00Z")
        self.assertEqual(kimi["availability_source"], "perplexity-model-menu")
        self.assertIsNone(kimi["last_verified_at"])
        self.assertEqual(claude_api["adapter_kind"], "api")
        self.assertEqual(claude_api["provider"], "anthropic")
        self.assertTrue(claude_api["reasoning_capable"])
        self.assertEqual(claude_api["timeout_seconds"], 120)
        self.assertEqual(claude_api["expected_latency_class"], "slow")
        self.assertEqual(claude_api["concurrency_limit"], 4)
        self.assertIsNone(claude_api["available"])
        self.assertEqual(claude_api["availability_status"], "static")
        self.assertIsNone(claude_api["last_verified_at"])
        self.assertTrue(gpt_api["reasoning_capable"])
        self.assertEqual(gpt_api["timeout_seconds"], 60)
        self.assertEqual(gpt_api["expected_latency_class"], "slow")
        self.assertEqual(gpt_api["concurrency_limit"], 4)
        self.assertEqual(gpt_api["provider"], "openai")
        self.assertEqual(gpt_api["availability_status"], "static")
        self.assertIsNone(gpt_api["last_verified_at"])
        self.assertEqual(payload["last_checked"], "2026-04-20T12:00:00Z")
        self.assertEqual(payload["source"], "perplexity-model-menu")

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
        app.state.task_repository = InMemoryTaskRepository()
        app.state.task_repository.save_model_catalog_snapshot(
            build_browser_catalog(
                ("Kimi K2.5", "GPT-5.4", "Best"),
                checked_at=datetime(2026, 3, 17, 18, 45, tzinfo=UTC),
                source="perplexity-model-menu",
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

        app.state.browser_adapter.automation = ObservedMenuAutomation()
        with TestClient(app) as client:
            response = client.get("/api/v1/models")

            self.assertEqual(response.status_code, 200)
            payload = response.json()["models"]
            kimi = next(item for item in payload if item["id"] == "kimi-k2-5")
            gpt = next(item for item in payload if item["id"] == "gpt-5-4")
            claude_api = next(item for item in payload if item["id"] == "claude-sonnet-4-6-api")
            self.assertEqual(kimi["availability_status"], "observed_unverified")
            self.assertEqual(kimi["available"], True)
            self.assertEqual(kimi["availability_source"], "perplexity-model-menu")
            self.assertEqual(kimi["availability_checked_at"], "2026-03-17T18:45:00Z")
            self.assertIsNone(kimi["last_verified_at"])
            self.assertEqual(gpt["availability_status"], "observed_available")
            self.assertEqual(gpt["available"], True)
            self.assertEqual(gpt["last_verified_at"], "2026-03-17T18:46:00Z")
            self.assertEqual(claude_api["availability_status"], "static")
            self.assertIsNone(claude_api["available"])

    def test_models_endpoint_downgrades_verified_browser_availability_after_newer_picker_failure(self) -> None:
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
        app.state.task_repository = InMemoryTaskRepository()
        app.state.task_repository.save_model_catalog_snapshot(
            build_browser_catalog(
                ("Kimi K2.5", "GPT-5.4", "Best"),
                checked_at=datetime(2026, 3, 17, 18, 45, tzinfo=UTC),
                source="perplexity-model-menu",
            )
        )

        class DriftedObservedMenuAutomation:
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
                    "last_model_picker_unavailable_at": datetime(2026, 3, 17, 18, 50, tzinfo=UTC),
                }

        app.state.browser_adapter.automation = DriftedObservedMenuAutomation()
        with TestClient(app) as client:
            response = client.get("/api/v1/models")

            self.assertEqual(response.status_code, 200)
            payload = response.json()["models"]
            kimi = next(item for item in payload if item["id"] == "kimi-k2-5")
            gpt = next(item for item in payload if item["id"] == "gpt-5-4")

            self.assertEqual(kimi["availability_status"], "observed_unverified")
            self.assertEqual(kimi["available"], True)
            self.assertEqual(kimi["availability_checked_at"], "2026-03-17T18:50:00Z")
            self.assertIsNone(kimi["last_verified_at"])

            self.assertEqual(gpt["availability_status"], "observed_unverified")
            self.assertEqual(gpt["available"], True)
            self.assertEqual(gpt["availability_checked_at"], "2026-03-17T18:50:00Z")
            self.assertEqual(gpt["last_verified_at"], "2026-03-17T18:46:00Z")

    def test_orchestrate_and_fetch_task_in_dry_run(self) -> None:
        response = self.client.post(
            "/api/v1/orchestrate",
            json={
                "prompt": "dry run prompt",
                "models": ["Kimi K2", "GPT-5.4 API"],
                "dry_run": True,
                "quorum": 1,
            },
        )

        self.assertEqual(response.status_code, 200)
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

    def test_stream_route_dry_run_fallback_emits_visible_output_and_persists_task(self) -> None:
        response = self.client.post(
            "/api/v1/orchestrate/stream",
            json={
                "prompt": "dry run stream prompt",
                "model": "Kimi K2",
                "dry_run": True,
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertIn("event: complete", response.text)
        self.assertIn("[dry-run] Simulated response for: dry run stream prompt", response.text)
        self.assertIn('"duration_ms": 0', response.text)

        recent = self.client.get("/api/v1/tasks", params={"limit": 1})

        self.assertEqual(recent.status_code, 200)
        payload = recent.json()
        self.assertEqual(len(payload), 1)
        self.assertEqual(payload[0]["adapter_name"], "dry-run")
        self.assertEqual(payload[0]["dry_run"], True)
        self.assertEqual(payload[0]["requested_models"][0]["id"], "kimi-k2-5")

    def test_stream_unknown_model_returns_sse_error(self) -> None:
        response = self.client.post(
            "/api/v1/orchestrate/stream",
            json={
                "prompt": "hello",
                "model": "nonexistent-xyz",
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertIn("event: error", response.text)
        self.assertIn("Unknown model: nonexistent-xyz", response.text)

    def test_stream_route_persists_completed_streaming_task(self) -> None:
        class StreamingAdapter:
            name = "api.openai"

            def execute_stream(self, request: ExecutionRequest) -> Iterator[StreamChunk]:
                yield StreamChunk(type="delta", text="stream ", model_id=request.step.model.id)
                yield StreamChunk(
                    type="complete",
                    text="stream result",
                    model_id=request.step.model.id,
                    details={"duration_ms": 7, "input_tokens": 11, "output_tokens": 13},
                )

        app = cast(Any, self.client.app)
        app.state.api_adapters["openai"] = StreamingAdapter()
        response = self.client.post(
            "/api/v1/orchestrate/stream",
            json={
                "prompt": "persist streamed task",
                "model": "GPT-5.4 API",
                "dry_run": False,
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertIn("event: accepted", response.text)
        self.assertIn("event: complete", response.text)

        accepted_data = next(
            line.removeprefix("data: ")
            for line in response.text.splitlines()
            if line.startswith("data: ") and '"task_id"' in line
        )
        task_id = json.loads(accepted_data)["task_id"]

        recent = self.client.get("/api/v1/tasks", params={"limit": 1})

        self.assertEqual(recent.status_code, 200)
        payload = recent.json()
        self.assertEqual(len(payload), 1)
        self.assertEqual(payload[0]["task_id"], task_id)
        self.assertEqual(payload[0]["adapter_name"], "api.openai")
        self.assertEqual(payload[0]["model"]["id"], "gpt-5-4-api")
        self.assertEqual(payload[0]["execution_mode"], "api")

        task = self.client.get(f"/api/v1/tasks/{task_id}")

        self.assertEqual(task.status_code, 200)
        task_payload = task.json()
        self.assertEqual(task_payload["output_text"], "stream result")
        self.assertEqual(len(task_payload["steps"]), 1)
        self.assertEqual(task_payload["steps"][0]["duration_ms"], 7)
        self.assertEqual(task_payload["steps"][0]["input_tokens"], 11)
        self.assertEqual(task_payload["steps"][0]["output_tokens"], 13)

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

        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(captured.output), 2)
        self.assertIn("orchestrate.request", captured.output[0])
        self.assertIn("dry_run=true", captured.output[0])
        self.assertIn("model_count=1", captured.output[0])
        self.assertIn('trace_id="route-trace-1"', captured.output[0])
        self.assertIn("orchestrate.accepted", captured.output[1])
        self.assertIn('status="completed"', captured.output[1])
        self.assertIn('trace_id="route-trace-1"', captured.output[1])
        self.assertEqual(response.headers.get("x-trace-id"), "route-trace-1")

    def test_orchestrate_without_trace_id_omits_header(self) -> None:
        response = self.client.post(
            "/api/v1/orchestrate",
            json={"prompt": "no trace", "model": "Kimi K2", "dry_run": True},
        )
        self.assertEqual(response.status_code, 200)
        self.assertNotIn("x-trace-id", response.headers)

    def test_orchestration_routes_offload_blocking_work_to_thread(self) -> None:
        async def run_sync(func: Callable[..., Any], /, *args: Any, **kwargs: Any) -> Any:
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

        self.assertEqual(submit.status_code, 200)
        self.assertEqual(recent.status_code, 200)
        self.assertEqual(task.status_code, 200)
        self.assertEqual(mocked.await_count, 2)  # submit_snapshot uses run_in_executor now; list+get remain

    def test_list_tasks_returns_recent_summaries_in_desc_order(self) -> None:
        first = self.client.post(
            "/api/v1/orchestrate",
            json={
                "prompt": "first task",
                "model": "Kimi K2",
                "dry_run": True,
            },
        )
        __import__("time").sleep(0.002)  # ensure distinct accepted_at on Windows (ms precision)
        second = self.client.post(
            "/api/v1/orchestrate",
            json={
                "prompt": "second task",
                "model": "GPT-5.4 API",
                "dry_run": True,
            },
        )

        self.assertEqual(first.status_code, 200)
        self.assertEqual(second.status_code, 200)

        response = self.client.get("/api/v1/tasks", params={"limit": 1})

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(len(payload), 1)
        self.assertEqual(payload[0]["task_id"], second.json()["task_id"])
        self.assertEqual(payload[0]["adapter_name"], "dry-run")
        self.assertIsNone(payload[0]["model"])
        self.assertEqual(payload[0]["dry_run"], True)
        self.assertEqual(payload[0]["model_count"], 1)
        self.assertEqual(payload[0]["requested_models"][0]["id"], "gpt-5-4-api")
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
            response = self.client.get("/api/v1/tasks/00000000-0000-0000-0000-ffffffffffff")

        self.assertEqual(response.status_code, 404)
        self.assertEqual(len(captured.output), 1)
        self.assertIn("task.get.not_found", captured.output[0])

    def test_list_tasks_can_filter_by_status_and_dry_run(self) -> None:
        client = TestClient(
            create_app(
                Settings(
                    env="test",
                    storage_backend="memory",
                    execution_profile="hybrid",
                    openai_api_key=None,
                    anthropic_api_key=None,
                    browser_enabled=False,
                    browser_profile_dir=None,
                )
            )
        )

        client.post(
            "/api/v1/orchestrate",
            json={
                "prompt": "dry run completed",
                "model": "Kimi K2",
                "dry_run": True,
            },
        )
        failed = client.post(
            "/api/v1/orchestrate",
            json={
                "prompt": "real failure",
                "model": "GPT-5.4 API",
                "dry_run": False,
            },
        )

        response = client.get(
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
        self.assertEqual(payload[0]["adapter_name"], "api.openai")
        self.assertEqual(payload[0]["status"], "failed")
        self.assertIsNone(payload[0]["model"])
        self.assertEqual(payload[0]["dry_run"], False)
        self.assertEqual(payload[0]["failure_code"], "provider_unavailable")
        self.assertEqual(payload[0]["requested_models"][0]["id"], "gpt-5-4-api")
        self.assertEqual(payload[0]["cancelled_step_count"], 0)
        self.assertIsNone(payload[0]["cancel_reason"])
        self.assertEqual(payload[0]["execution_mode"], "api")

    def test_list_tasks_exposes_winning_model_and_short_circuit_summary(self) -> None:
        from time import monotonic, sleep

        from gracekelly.core.contracts import (
            ExecutionAdapter,
            ExecutionMode,
            ExecutionResult,
            FailureCode,
            StepStatus,
        )

        class SlowCancellableAdapter(ExecutionAdapter):
            name = "api.openai"

            def execute(self, request: Any) -> ExecutionResult:
                deadline = monotonic() + 0.25
                while monotonic() < deadline:
                    if request.cancellation and request.cancellation.is_cancelled:
                        return ExecutionResult(
                            adapter_name=self.name,
                            model_id=request.step.model.id,
                            model_display_name=request.step.model.display_name,
                            execution_mode=ExecutionMode.API,
                            status=StepStatus.CANCELLED,
                            details={"cancelled": True},
                        )
                    sleep(0.005)
                return ExecutionResult(
                    adapter_name=self.name,
                    model_id=request.step.model.id,
                    model_display_name=request.step.model.display_name,
                    execution_mode=ExecutionMode.API,
                    status=StepStatus.FAILED,
                    failure_code=FailureCode.TIMEOUT,
                    failure_message="Cancellation was not observed in time.",
                )

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
        app.state.api_adapters["openai"] = SlowCancellableAdapter()
        client = TestClient(app)

        response = client.post(
            "/api/v1/orchestrate",
            json={
                "prompt": "short circuit summary",
                "models": ["Kimi K2", "GPT-5.4 API"],
                "dry_run": False,
                "quorum": 1,
                "merge_strategy": "first_success",
                "cancel_on_quorum": True,
            },
        )

        self.assertEqual(response.status_code, 200)

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
        client = TestClient(
            create_app(
                Settings(
                    env="test",
                    storage_backend="memory",
                    execution_profile="hybrid",
                    openai_api_key=None,
                    anthropic_api_key=None,
                    browser_enabled=False,
                    browser_profile_dir=None,
                )
            )
        )

        response = client.post(
            "/api/v1/orchestrate",
            json={
                "prompt": "openai without key",
                "model": "GPT-5.4 API",
                "dry_run": False,
            },
        )

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["status"], "failed")
        self.assertEqual(payload["adapter_name"], "api.openai")
        self.assertEqual(payload["failure_code"], "provider_unavailable")
        self.assertEqual(payload["model"], None)
        self.assertNotIn("steps", payload)

    def test_orchestrate_rejects_unknown_merge_strategy(self) -> None:
        response = self.client.post(
            "/api/v1/orchestrate",
            json={
                "prompt": "bad strategy",
                "model": "GPT-5.4 API",
                "merge_strategy": "fanout",
            },
        )

        self.assertEqual(response.status_code, 422)

    def test_orchestrate_returns_storage_failed_when_task_persistence_breaks(self) -> None:
        class SaveFailingRepository(InMemoryTaskRepository):
            def save_task_with_steps(self, task: TaskRecord, steps: list[TaskStepRecord]) -> None:
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
            def get(self, task_id: str) -> TaskRecord | None:
                raise RuntimeError("database is offline")

        client = self._build_client_with_repository(ReadFailingRepository())

        response = client.get("/api/v1/tasks/00000000-0000-0000-0000-000000000123")

        self.assertEqual(response.status_code, 503)
        payload = response.json()
        self.assertEqual(payload["detail"]["code"], "storage_failed")
        self.assertIn("get_task", payload["detail"]["message"])

    def test_list_tasks_returns_storage_failed_when_repository_read_breaks(self) -> None:
        class ListFailingRepository(InMemoryTaskRepository):
            def list_recent(self, limit: int, **kwargs: Any) -> list[TaskRecord]:
                raise RuntimeError("database is offline")

        client = self._build_client_with_repository(ListFailingRepository())

        response = client.get("/api/v1/tasks")

        self.assertEqual(response.status_code, 503)
        payload = response.json()
        self.assertEqual(payload["detail"]["code"], "storage_failed")
        self.assertIn("list_recent_tasks", payload["detail"]["message"])

    def test_orchestrate_preserves_requested_models_when_event_persistence_fails(self) -> None:
        class EventFailingRepository(InMemoryTaskRepository):
            def append_event(self, event: TaskEventRecord) -> None:
                raise RuntimeError("event sink offline")

        client = self._build_client_with_repository(EventFailingRepository())

        response = client.post(
            "/api/v1/orchestrate",
            json={
                "prompt": "dry run with event failure",
                "models": ["Kimi K2", "GPT-5.4 API"],
                "dry_run": True,
            },
        )

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual([item["id"] for item in payload["requested_models"]], ["kimi-k2-5", "gpt-5-4-api"])

    def test_orchestrate_summary_does_not_depend_on_post_write_readback(self) -> None:
        class ReadbackFailingRepository(InMemoryTaskRepository):
            def list_steps(self, task_id: str) -> list[TaskStepRecord]:
                raise RuntimeError("read path offline")

            def list_events(self, task_id: str) -> list[TaskEventRecord]:
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

        self.assertEqual(response.status_code, 200)
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
                "models": ["Kimi K2", "GPT-5.4 API"],
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
                "model": "Sonar",
                "reasoning": True,
            },
        )

        self.assertEqual(response.status_code, 422)
        self.assertIn("reasoning=true is not supported", response.json()["detail"])

    def test_orchestrate_returns_not_implemented_when_submit_snapshot_rejects_capability(self) -> None:
        with patch.object(
            OrchestratorService,
            "submit_snapshot",
            side_effect=NotImplementedError("requested capability is not wired"),
        ):
            response = self.client.post(
                "/api/v1/orchestrate",
                json={
                    "prompt": "not implemented",
                    "model": "Kimi K2",
                    "dry_run": True,
                },
            )

        self.assertEqual(response.status_code, 501)
        self.assertEqual(response.json()["detail"], "Requested capability is not available.")

    def test_orchestrate_returns_traceable_500_when_submit_snapshot_crashes(self) -> None:
        with TestClient(self.client.app, raise_server_exceptions=False) as client:
            with self.assertLogs("gracekelly.api.routes.orchestrate", level="ERROR") as captured:
                with patch.object(
                    OrchestratorService,
                    "submit_snapshot",
                    side_effect=RuntimeError("unexpected crash"),
                ):
                    response = client.post(
                        "/api/v1/orchestrate",
                        json={
                            "prompt": "boom",
                            "model": "Kimi K2",
                            "dry_run": True,
                            "metadata": {"trace_id": "trace-json-500"},
                        },
                    )

        self.assertEqual(response.status_code, 500)
        payload = response.json()
        self.assertEqual(payload["detail"]["code"], "unknown_error")
        self.assertEqual(payload["detail"]["trace_id"], "trace-json-500")
        self.assertEqual(payload["detail"]["message"], "Internal server error.")
        self.assertIn("unexpected crash", captured.output[0])

    def test_orchestrate_response_does_not_reresolve_requested_models_after_submit(self) -> None:
        from gracekelly.core.contracts import AdapterHint, ExecutionMode, MergeStrategy, StepStatus, TaskStatus
        from gracekelly.core.models import clear_browser_catalog, install_browser_catalog
        from gracekelly.core.orchestrator import SubmissionSnapshot

        snapshot = SubmissionSnapshot(
            task=TaskRecord(
                task_id="task-orchestrate-catalog-drift",
                status=TaskStatus.COMPLETED,
                accepted_at=datetime(2026, 4, 20, 12, 0, tzinfo=UTC),
                completed_at=datetime(2026, 4, 20, 12, 0, tzinfo=UTC),
                duration_ms=25,
                prompt="catalog drift",
                reasoning=False,
                execution_mode=ExecutionMode.BROWSER,
                dry_run=False,
                model_count=1,
                quorum=1,
                merge_strategy=MergeStrategy.FIRST_SUCCESS,
                adapter_hint=AdapterHint.AUTO,
                cancel_on_quorum=True,
                output_text="browser answer",
            ),
            steps=[
                TaskStepRecord(
                    task_id="task-orchestrate-catalog-drift",
                    step_index=1,
                    model_id="kimi-k2-5",
                    model_display_name="Kimi K2.5",
                    backend="browser",
                    provider="perplexity",
                    status=StepStatus.COMPLETED,
                    output_text="browser answer",
                    duration_ms=25,
                )
            ],
        )
        catalog_snapshot = build_browser_catalog(
            ("Kimi K2.5",),
            checked_at=datetime(2026, 4, 20, 12, 0, tzinfo=UTC),
            source="test-fixture",
        )

        def submit_snapshot_and_clear_catalog(*args: Any, **kwargs: Any) -> Any:
            clear_browser_catalog()
            return snapshot

        try:
            install_browser_catalog(catalog_snapshot)
            with TestClient(self.client.app, raise_server_exceptions=False) as client:
                with patch.object(
                    OrchestratorService,
                    "submit_snapshot",
                    side_effect=submit_snapshot_and_clear_catalog,
                ):
                    response = client.post(
                        "/api/v1/orchestrate",
                        json={
                            "prompt": "catalog drift",
                            "model": "Kimi K2",
                            "dry_run": False,
                        },
                    )
        finally:
            install_browser_catalog(catalog_snapshot)

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["requested_models"], [{"id": "kimi-k2-5", "display_name": "Kimi K2.5"}])
        self.assertEqual(payload["output_text"], "browser answer")

    def test_upload_accepts_text_file_and_models_form_value(self) -> None:
        response = self.client.post(
            "/api/v1/orchestrate/upload",
            data={
                "prompt": "Summarize this",
                "models": '["Kimi K2", "GPT-5.4 API"]',
                "dry_run": "true",
            },
            files=[("files", ("notes.txt", b"Hello world content", "text/plain"))],
        )

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual([item["id"] for item in payload["requested_models"]], ["kimi-k2-5", "gpt-5-4-api"])

        task = self.client.get(f"/api/v1/tasks/{payload['task_id']}")
        self.assertEqual(task.status_code, 200)
        self.assertIn("Summarize this", task.json()["prompt"])
        self.assertIn("[File: notes.txt]", task.json()["prompt"])

    def test_upload_rejects_invalid_models_json(self) -> None:
        response = self.client.post(
            "/api/v1/orchestrate/upload",
            data={
                "prompt": "bad models",
                "models": "not-json",
                "dry_run": "true",
            },
        )

        self.assertEqual(response.status_code, 422)
        self.assertEqual(response.json()["detail"], "Field 'models' must be a JSON array of strings.")

    def test_upload_rejects_non_string_models_json_array(self) -> None:
        response = self.client.post(
            "/api/v1/orchestrate/upload",
            data={
                "prompt": "bad models",
                "models": "[1]",
                "dry_run": "true",
            },
        )

        self.assertEqual(response.status_code, 422)
        self.assertEqual(response.json()["detail"], "Field 'models' must be a JSON array of strings.")

    def test_upload_pdf_without_pypdf_returns_422(self) -> None:
        real_import = __import__

        def import_without_pypdf(
            name: str,
            globals: dict[str, object] | None = None,
            locals: dict[str, object] | None = None,
            fromlist: tuple[str, ...] = (),
            level: int = 0,
        ) -> Any:
            if name == "pypdf":
                raise ImportError("missing pypdf")
            return real_import(name, globals, locals, fromlist, level)

        with patch("builtins.__import__", side_effect=import_without_pypdf):
            response = self.client.post(
                "/api/v1/orchestrate/upload",
                data={"prompt": "Read PDF", "model": "Kimi K2", "dry_run": "true"},
                files=[("files", ("doc.pdf", b"%PDF-1.4", "application/pdf"))],
            )

        self.assertEqual(response.status_code, 422)
        self.assertIn("pypdf", response.json()["detail"])

    def test_upload_pdf_parse_failure_returns_422(self) -> None:
        class BrokenPdfReader:
            def __init__(self, _stream: Any) -> None:
                raise RuntimeError("cannot read pdf")

        fake_pypdf = type("FakePyPdf", (), {"PdfReader": BrokenPdfReader})

        with patch.dict(sys.modules, {"pypdf": fake_pypdf}):
            response = self.client.post(
                "/api/v1/orchestrate/upload",
                data={"prompt": "Read PDF", "model": "Kimi K2", "dry_run": "true"},
                files=[("files", ("doc.pdf", b"%PDF-1.4", "application/pdf"))],
            )

        self.assertEqual(response.status_code, 422)
        self.assertEqual(response.json()["detail"], "Cannot extract text from PDF: doc.pdf")

    def test_upload_timeout_returns_504_when_executor_exceeds_timeout(self) -> None:
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
                orchestrate_timeout_seconds=0.01,
            )
        )
        png_bytes = (
            b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01"
            b"\x00\x00\x00\x01\x08\x02\x00\x00\x00\x90wS\xde\x00\x00"
            b"\x00\x0cIDATx\x9cc\xf8\x0f\x00\x00\x01\x01\x00\x05\x18"
            b"\xd8N\x00\x00\x00\x00IEND\xaeB`\x82"
        )

        with TestClient(app) as client:
            with patch("gracekelly.api.routes.orchestrate.asyncio.wait_for", side_effect=TimeoutError):
                response = client.post(
                    "/api/v1/orchestrate/upload",
                    data={"prompt": "Describe this image", "model": "Kimi K2", "dry_run": "true"},
                    files=[("files", ("photo.png", png_bytes, "image/png"))],
                )

        self.assertEqual(response.status_code, 504)
        self.assertEqual(response.json()["detail"], "Orchestration request timed out.")

    def test_upload_returns_storage_failed_when_submit_snapshot_raises(self) -> None:
        with patch.object(
            OrchestratorService,
            "submit_snapshot",
            side_effect=StorageUnavailableError("save_task_with_steps", "database offline"),
        ):
            response = self.client.post(
                "/api/v1/orchestrate/upload",
                data={"prompt": "storage failure", "model": "Kimi K2", "dry_run": "true"},
            )

        self.assertEqual(response.status_code, 503)
        self.assertEqual(response.json()["detail"]["code"], "storage_failed")

    def test_upload_returns_validation_error_when_submit_snapshot_raises(self) -> None:
        with patch.object(
            OrchestratorService,
            "submit_snapshot",
            side_effect=ValueError("Unsupported merge strategy: fanout"),
        ):
            response = self.client.post(
                "/api/v1/orchestrate/upload",
                data={"prompt": "bad request", "model": "Kimi K2", "dry_run": "true"},
            )

        self.assertEqual(response.status_code, 422)
        self.assertEqual(response.json()["detail"], "Unsupported merge strategy: fanout")

    def test_upload_returns_not_implemented_when_submit_snapshot_raises(self) -> None:
        with patch.object(
            OrchestratorService,
            "submit_snapshot",
            side_effect=NotImplementedError("upload not supported"),
        ):
            response = self.client.post(
                "/api/v1/orchestrate/upload",
                data={"prompt": "not implemented", "model": "Kimi K2", "dry_run": "true"},
            )

        self.assertEqual(response.status_code, 501)
        self.assertEqual(response.json()["detail"], "Requested capability is not available.")

    def test_upload_returns_traceable_500_when_submit_snapshot_crashes(self) -> None:
        with TestClient(self.client.app, raise_server_exceptions=False) as client:
            with self.assertLogs("gracekelly.api.routes.orchestrate", level="ERROR") as captured:
                with patch.object(
                    OrchestratorService,
                    "submit_snapshot",
                    side_effect=RuntimeError("upload crash"),
                ):
                    response = client.post(
                        "/api/v1/orchestrate/upload",
                        data={"prompt": "boom", "model": "Kimi K2", "dry_run": "true"},
                    )

        self.assertEqual(response.status_code, 500)
        payload = response.json()
        trace_id = payload["detail"]["trace_id"]
        self.assertTrue(trace_id)
        self.assertEqual(payload["detail"]["code"], "unknown_error")
        self.assertEqual(payload["detail"]["message"], "Internal server error.")
        self.assertIn("upload crash", captured.output[0])

    def test_upload_response_does_not_reresolve_requested_models_after_submit(self) -> None:
        from gracekelly.core.contracts import AdapterHint, ExecutionMode, MergeStrategy, StepStatus, TaskStatus
        from gracekelly.core.models import clear_browser_catalog, install_browser_catalog
        from gracekelly.core.orchestrator import SubmissionSnapshot

        snapshot = SubmissionSnapshot(
            task=TaskRecord(
                task_id="task-upload-catalog-drift",
                status=TaskStatus.COMPLETED,
                accepted_at=datetime(2026, 4, 20, 12, 0, tzinfo=UTC),
                completed_at=datetime(2026, 4, 20, 12, 0, tzinfo=UTC),
                duration_ms=30,
                prompt="catalog drift upload",
                reasoning=False,
                execution_mode=ExecutionMode.BROWSER,
                dry_run=False,
                model_count=1,
                quorum=1,
                merge_strategy=MergeStrategy.FIRST_SUCCESS,
                adapter_hint=AdapterHint.AUTO,
                cancel_on_quorum=True,
                output_text="upload browser answer",
            ),
            steps=[
                TaskStepRecord(
                    task_id="task-upload-catalog-drift",
                    step_index=1,
                    model_id="kimi-k2-5",
                    model_display_name="Kimi K2.5",
                    backend="browser",
                    provider="perplexity",
                    status=StepStatus.COMPLETED,
                    output_text="upload browser answer",
                    duration_ms=30,
                )
            ],
        )
        catalog_snapshot = build_browser_catalog(
            ("Kimi K2.5",),
            checked_at=datetime(2026, 4, 20, 12, 0, tzinfo=UTC),
            source="test-fixture",
        )

        def submit_snapshot_and_clear_catalog(*args: Any, **kwargs: Any) -> Any:
            clear_browser_catalog()
            return snapshot

        try:
            install_browser_catalog(catalog_snapshot)
            with TestClient(self.client.app, raise_server_exceptions=False) as client:
                with patch.object(
                    OrchestratorService,
                    "submit_snapshot",
                    side_effect=submit_snapshot_and_clear_catalog,
                ):
                    response = client.post(
                        "/api/v1/orchestrate/upload",
                        data={
                            "prompt": "catalog drift upload",
                            "model": "Kimi K2",
                            "dry_run": "false",
                        },
                    )
        finally:
            install_browser_catalog(catalog_snapshot)

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["requested_models"], [{"id": "kimi-k2-5", "display_name": "Kimi K2.5"}])
        self.assertEqual(payload["output_text"], "upload browser answer")

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

        self.assertEqual(response.status_code, 200)
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
                "metadata": {"trace_id": "auth-trace-1"},
            },
        )

        self.assertEqual(response.status_code, 503)
        payload = response.json()
        self.assertEqual(payload["detail"]["code"], "model_auth_required")
        self.assertEqual(payload["detail"]["message"], "Scripted browser session is logged out.")
        self.assertEqual(payload["detail"]["trace_id"], "auth-trace-1")

        recent = client.get("/api/v1/tasks", params={"limit": 1})
        self.assertEqual(recent.status_code, 200)
        task_id = recent.json()[0]["task_id"]

        task = client.get(f"/api/v1/tasks/{task_id}")
        self.assertEqual(task.status_code, 200)
        task_payload = task.json()
        self.assertEqual(task_payload["status"], "failed")
        self.assertEqual(task_payload["failure_code"], "auth_failed")
        self.assertEqual(task_payload["metadata"]["trace_id"], "auth-trace-1")
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

    def test_browser_auth_failure_stream_persists_trace_id_for_task_polling(self) -> None:
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
            "/api/v1/orchestrate/stream",
            json={
                "prompt": "browser auth stream failure",
                "model": "Kimi K2",
                "dry_run": False,
            },
        )

        self.assertEqual(response.status_code, 200)
        task_id = next(
            json.loads(line.removeprefix("data: "))["task_id"]
            for line in response.text.splitlines()
            if line.startswith("data: ") and '"task_id"' in line
        )

        task = client.get(f"/api/v1/tasks/{task_id}")

        self.assertEqual(task.status_code, 200)
        task_payload = task.json()
        self.assertEqual(task_payload["status"], "failed")
        self.assertEqual(task_payload["failure_code"], "auth_failed")
        self.assertIn("trace_id", task_payload["metadata"])
        self.assertTrue(task_payload["metadata"]["trace_id"])


    def test_retry_failed_task_creates_new_task_with_linkage(self) -> None:
        submit = self.client.post(
            "/api/v1/orchestrate",
            json={
                "prompt": "retry me",
                "model": "Kimi K2",
                "dry_run": True,
            },
        )
        self.assertEqual(submit.status_code, 200)
        original_id = submit.json()["task_id"]

        # Patch the original task to "failed" for retry
        app = cast(Any, self.client.app)
        repo = cast(Any, app.state.orchestrator_service)._repository
        task = repo.get(original_id)
        from gracekelly.core.contracts import FailureCode, TaskStatus
        task.status = TaskStatus.FAILED
        task.failure_code = FailureCode.TIMEOUT
        task.failure_message = "timed out"

        retry = self.client.post(f"/api/v1/tasks/{original_id}/retry")
        self.assertEqual(retry.status_code, 200)
        retry_payload = retry.json()
        self.assertNotEqual(retry_payload["task_id"], original_id)

        retry_detail = self.client.get(f"/api/v1/tasks/{retry_payload['task_id']}")
        self.assertEqual(retry_detail.status_code, 200)
        self.assertEqual(retry_detail.json()["retry_of_task_id"], original_id)

    def test_retry_completed_task_returns_409(self) -> None:
        submit = self.client.post(
            "/api/v1/orchestrate",
            json={
                "prompt": "completed task",
                "model": "Kimi K2",
                "dry_run": True,
            },
        )
        self.assertEqual(submit.status_code, 200)
        task_id = submit.json()["task_id"]

        retry = self.client.post(f"/api/v1/tasks/{task_id}/retry")
        self.assertEqual(retry.status_code, 409)

    def test_invalid_uuid_task_id_returns_422(self) -> None:
        response = self.client.get("/api/v1/tasks/not-a-uuid")
        self.assertEqual(response.status_code, 422)

    def test_retry_nonexistent_task_returns_404(self) -> None:
        retry = self.client.post("/api/v1/tasks/00000000-0000-0000-0000-000000000000/retry")
        self.assertEqual(retry.status_code, 404)

    def test_export_task_returns_storage_failed_when_repository_is_unavailable(self) -> None:
        with patch.object(
            OrchestratorService,
            "get_task",
            side_effect=StorageUnavailableError("get_task", "database offline"),
        ):
            response = self.client.get("/api/v1/tasks/00000000-0000-0000-0000-000000000123/export")

        self.assertEqual(response.status_code, 503)
        self.assertEqual(response.json()["detail"]["code"], "storage_failed")

    def test_retry_returns_storage_failed_when_loading_original_task_fails(self) -> None:
        with patch.object(
            OrchestratorService,
            "get_task",
            side_effect=StorageUnavailableError("get_task", "database offline"),
        ):
            response = self.client.post("/api/v1/tasks/00000000-0000-0000-0000-000000000123/retry")

        self.assertEqual(response.status_code, 503)
        self.assertEqual(response.json()["detail"]["code"], "storage_failed")

    def test_retry_returns_storage_failed_when_retry_submission_fails(self) -> None:
        submit = self.client.post(
            "/api/v1/orchestrate",
            json={
                "prompt": "retry storage failure",
                "model": "Kimi K2",
                "dry_run": True,
            },
        )
        self.assertEqual(submit.status_code, 200)
        original_id = submit.json()["task_id"]

        app = cast(Any, self.client.app)
        repo = cast(Any, app.state.orchestrator_service)._repository
        task = repo.get(original_id)
        from gracekelly.core.contracts import FailureCode, TaskStatus
        task.status = TaskStatus.FAILED
        task.failure_code = FailureCode.TIMEOUT
        task.failure_message = "timed out"

        with patch.object(
            OrchestratorService,
            "submit_snapshot",
            side_effect=StorageUnavailableError("save_task_with_steps", "database offline"),
        ):
            retry = self.client.post(f"/api/v1/tasks/{original_id}/retry")

        self.assertEqual(retry.status_code, 503)
        self.assertEqual(retry.json()["detail"]["code"], "storage_failed")

    def test_retry_returns_validation_error_when_retry_submission_fails(self) -> None:
        submit = self.client.post(
            "/api/v1/orchestrate",
            json={
                "prompt": "retry validation failure",
                "model": "Kimi K2",
                "dry_run": True,
            },
        )
        self.assertEqual(submit.status_code, 200)
        original_id = submit.json()["task_id"]

        app = cast(Any, self.client.app)
        repo = cast(Any, app.state.orchestrator_service)._repository
        task = repo.get(original_id)
        from gracekelly.core.contracts import FailureCode, TaskStatus
        task.status = TaskStatus.FAILED
        task.failure_code = FailureCode.TIMEOUT
        task.failure_message = "timed out"

        with patch.object(
            OrchestratorService,
            "submit_snapshot",
            side_effect=ValueError("Metadata trace_id must be a string."),
        ):
            retry = self.client.post(f"/api/v1/tasks/{original_id}/retry")

        self.assertEqual(retry.status_code, 422)
        self.assertEqual(retry.json()["detail"], "Metadata trace_id must be a string.")


if __name__ == "__main__":
    unittest.main()
