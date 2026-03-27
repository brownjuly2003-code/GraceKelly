from __future__ import annotations

import unittest

from gracekelly.adapters.browser.perplexity import PerplexityBrowserAdapter
from gracekelly.adapters.browser.session import BrowserSessionConfig, BrowserSessionManager
from gracekelly.adapters.dry_run import DryRunExecutionAdapter
from gracekelly.core.execution_profile import resolve_execution_profile
from gracekelly.core.readiness import SupportsHealthcheck, build_readiness_report
from gracekelly.core.router import ExecutionRouter
from gracekelly.storage.memory import InMemoryTaskRepository


class ReadinessTests(unittest.TestCase):
    def test_build_readiness_report_keeps_optional_browser_out_of_overall_status(self) -> None:
        repository = InMemoryTaskRepository()
        browser_adapter = PerplexityBrowserAdapter(
            session_manager=BrowserSessionManager(
                BrowserSessionConfig(
                    enabled=False,
                    provider="perplexity",
                    base_url="https://www.perplexity.ai",
                    profile_dir=None,
                )
            )
        )
        report = build_readiness_report(
            environment="test",
            profile=resolve_execution_profile("dry-run"),
            repository=repository,
            adapters={
                "dry-run": DryRunExecutionAdapter(),
                "browser.perplexity": browser_adapter,
            },
        )

        self.assertEqual(report["status"], "ok")
        self.assertEqual(report["components"][0]["kind"], "storage")
        browser_component = next(item for item in report["components"] if item["name"] == "browser.perplexity")
        self.assertFalse(browser_component["required"])

    def test_build_readiness_report_marks_required_browser_as_degraded_in_hybrid(self) -> None:
        repository = InMemoryTaskRepository()
        browser_adapter = PerplexityBrowserAdapter(
            session_manager=BrowserSessionManager(
                BrowserSessionConfig(
                    enabled=False,
                    provider="perplexity",
                    base_url="https://www.perplexity.ai",
                    profile_dir=None,
                )
            )
        )
        report = build_readiness_report(
            environment="test",
            profile=resolve_execution_profile("hybrid"),
            repository=repository,
            adapters={
                "dry-run": DryRunExecutionAdapter(),
                "browser.perplexity": browser_adapter,
            },
        )

        self.assertEqual(report["status"], "degraded")
        browser_component = next(item for item in report["components"] if item["name"] == "browser.perplexity")
        self.assertTrue(browser_component["required"])

    def test_build_readiness_report_degrades_when_storage_schema_report_is_degraded(self) -> None:
        class SchemaDriftRepository(InMemoryTaskRepository):
            def schema_report(self) -> dict[str, object]:
                return {
                    "status": "degraded",
                    "backend": self.backend_name,
                    "missing_tables": ["gk_task_steps"],
                }

        report = build_readiness_report(
            environment="test",
            profile=resolve_execution_profile("dry-run"),
            repository=SchemaDriftRepository(),
            adapters={
                "dry-run": DryRunExecutionAdapter(),
            },
        )

        self.assertEqual(report["status"], "degraded")
        storage_component = next(item for item in report["components"] if item["kind"] == "storage")
        self.assertEqual(storage_component["status"], "degraded")
        self.assertEqual(storage_component["details"]["schema"]["missing_tables"], ["gk_task_steps"])

    def test_build_readiness_report_includes_execution_component_details(self) -> None:
        report = build_readiness_report(
            environment="test",
            profile=resolve_execution_profile("dry-run"),
            repository=InMemoryTaskRepository(),
            adapters={
                "dry-run": DryRunExecutionAdapter(),
            },
            execution_router=ExecutionRouter(dry_run_adapter=DryRunExecutionAdapter()),
        )

        execution = next(item for item in report["components"] if item["kind"] == "execution")

        self.assertTrue(execution["required"])
        self.assertEqual(execution["status"], "ok")
        self.assertEqual(execution["details"]["active_model_executions"], 0)
        self.assertEqual(execution["details"]["saturated_models"], [])
        self.assertEqual(execution["details"]["model_limits"]["kimi-k2-5"], 1)

    def test_build_readiness_report_surfaces_open_browser_circuit_breaker(self) -> None:
        class OpenBreakerAdapter:
            def healthcheck(self) -> dict[str, object]:
                return {
                    "status": "degraded",
                    "adapter_name": "browser.perplexity",
                    "circuit_breaker": {
                        "enabled": True,
                        "state": "open",
                        "failure_threshold": 3,
                        "cooldown_seconds": 60,
                    },
                }

        report = build_readiness_report(
            environment="test",
            profile=resolve_execution_profile("hybrid"),
            repository=InMemoryTaskRepository(),
            adapters={
                "dry-run": DryRunExecutionAdapter(),
                "browser.perplexity": OpenBreakerAdapter(),
            },
        )

        browser_component = next(item for item in report["components"] if item["name"] == "browser.perplexity")

        self.assertEqual(report["status"], "degraded")
        self.assertEqual(browser_component["status"], "degraded")
        self.assertEqual(browser_component["details"]["circuit_breaker"]["state"], "open")


    def test_adapter_with_healthcheck_satisfies_protocol(self) -> None:
        self.assertIsInstance(DryRunExecutionAdapter(), SupportsHealthcheck)

    def test_object_without_healthcheck_does_not_satisfy_protocol(self) -> None:
        self.assertNotIsInstance(object(), SupportsHealthcheck)

    def test_readiness_with_non_healthcheck_adapter_shows_unknown(self) -> None:
        report = build_readiness_report(
            environment="test",
            profile=resolve_execution_profile("dry-run"),
            repository=InMemoryTaskRepository(),
            adapters={
                "dry-run": object(),
            },
        )
        dry_run_component = next(item for item in report["components"] if item["name"] == "dry-run")
        self.assertEqual(dry_run_component["status"], "unknown")


if __name__ == "__main__":
    unittest.main()
