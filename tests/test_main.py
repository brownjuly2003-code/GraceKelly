from __future__ import annotations

import unittest
from unittest.mock import patch

from fastapi.testclient import TestClient

from gracekelly.config import Settings
from gracekelly.main import build_browser_adapter, build_browser_automation, build_task_repository, create_app


class MainWiringTests(unittest.TestCase):
    def test_build_task_repository_passes_connect_timeout_to_postgres(self) -> None:
        captured: dict[str, object] = {}

        class FakeRepository:
            def __init__(self, dsn: str, *, bootstrap: bool, connect_timeout_seconds: int) -> None:
                captured["dsn"] = dsn
                captured["bootstrap"] = bootstrap
                captured["connect_timeout_seconds"] = connect_timeout_seconds

        settings = Settings(
            storage_backend="postgres",
            postgres_dsn="postgresql://example",
            postgres_connect_timeout_seconds=9,
        )

        with patch("gracekelly.storage.postgres.PostgresTaskRepository", FakeRepository):
            repository = build_task_repository(settings)

        self.assertIsInstance(repository, FakeRepository)
        self.assertEqual(captured["dsn"], "postgresql://example")
        self.assertEqual(captured["bootstrap"], True)
        self.assertEqual(captured["connect_timeout_seconds"], 9)

    def test_create_app_registers_openai_adapter(self) -> None:
        app = create_app(
            Settings(
                storage_backend="memory",
                openai_api_key="test-key",
                openai_base_url="https://example.test/v1",
                openai_timeout_seconds=45.0,
            )
        )

        self.assertIn("openai", app.state.api_adapters)
        self.assertEqual(app.state.api_adapters["openai"].name, "api.openai")
        self.assertIn("api.openai", app.state.adapter_registry)

    def test_build_browser_automation_supports_playwright_backend(self) -> None:
        automation = build_browser_automation(
            Settings(
                storage_backend="memory",
                browser_automation_backend="playwright",
                browser_playwright_channel="msedge",
                browser_playwright_headless=True,
            )
        )

        self.assertEqual(type(automation).__name__, "PlaywrightBrowserAutomation")
        self.assertEqual(automation.healthcheck()["channel"], "msedge")
        self.assertTrue(automation.healthcheck()["headless"])

    def test_build_browser_adapter_wraps_perplexity_with_circuit_breaker(self) -> None:
        adapter = build_browser_adapter(
            Settings(
                storage_backend="memory",
                browser_enabled=True,
                browser_profile_dir=r"D:\Profiles\GraceKelly",
                browser_circuit_breaker_enabled=True,
                browser_circuit_breaker_failure_threshold=4,
                browser_circuit_breaker_cooldown_seconds=90,
            )
        )

        health = adapter.healthcheck()

        self.assertEqual(adapter.name, "browser.perplexity")
        self.assertIn("circuit_breaker", health)
        self.assertTrue(health["circuit_breaker"]["enabled"])
        self.assertEqual(health["circuit_breaker"]["failure_threshold"], 4)
        self.assertEqual(health["circuit_breaker"]["cooldown_seconds"], 90)

    def test_app_lifespan_closes_browser_automation(self) -> None:
        closed = {"value": False}

        class ClosableAdapter:
            async def close(self) -> None:
                closed["value"] = True

        with patch("gracekelly.main.build_browser_adapter", return_value=ClosableAdapter()):
            app = create_app(Settings(storage_backend="memory"))
            with TestClient(app):
                self.assertFalse(closed["value"])

        self.assertTrue(closed["value"])
