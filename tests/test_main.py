from __future__ import annotations

import unittest
from unittest.mock import patch

from gracekelly.config import Settings
from gracekelly.main import build_task_repository, create_app


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
