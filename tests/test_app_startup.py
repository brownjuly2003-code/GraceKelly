from __future__ import annotations

import asyncio
import logging
import tempfile
import unittest
from pathlib import Path
from unittest.mock import AsyncMock, patch

import httpx
import pytest

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
class AppStartupTests(unittest.TestCase):
    def test_default_startup_succeeds(self) -> None:
        app = create_app(Settings(
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
            anthropic_api_key=None,
            anthropic_base_url="https://api.anthropic.com",
            anthropic_timeout_seconds=1.0,
            browser_enabled=False,
            browser_profile_dir=None,
            browser_base_url="https://www.perplexity.ai",
        ))
        client = TestClient(app)
        health = client.get("/health")
        self.assertEqual(health.status_code, 200)
        self.assertIn("status", health.json())

    def test_app_factory_returns_fresh_instance(self) -> None:
        from gracekelly.main import app_factory
        app1 = app_factory()
        app2 = app_factory()
        self.assertIsNot(app1, app2)


@unittest.skipIf(create_app is None, "fastapi.testclient is not installed")
class AppStartupAsyncTests(unittest.IsolatedAsyncioTestCase):
    async def test_startup_refreshes_catalog_when_sync_refresh_requires_no_running_loop(self) -> None:
        from gracekelly.core.models import clear_browser_catalog
        from gracekelly.storage.memory import InMemoryTaskRepository

        class _LoopGuardBrowserAdapter:
            name = "browser.perplexity"

            def execute(self, request: object) -> object:
                raise NotImplementedError

            def refresh_model_catalog(self) -> tuple[str, ...]:
                try:
                    asyncio.get_running_loop()
                except RuntimeError:
                    return ("Best", "Kimi K2")
                raise RuntimeError("It looks like you are using Playwright Sync API inside the asyncio loop.")

            def healthcheck(self) -> dict[str, object]:
                return {
                    "status": "ok",
                    "adapter_name": self.name,
                }

        clear_browser_catalog()
        repository = InMemoryTaskRepository()

        with patch("gracekelly.main.build_task_repository", return_value=repository), patch(
            "gracekelly.main.build_browser_adapter",
            return_value=_LoopGuardBrowserAdapter(),
        ):
            app = create_app(Settings(storage_backend="memory", browser_enabled=True, browser_automation_backend="null"))
            try:
                async with app.router.lifespan_context(app):
                    async with httpx.AsyncClient(
                        transport=httpx.ASGITransport(app=app),
                        base_url="http://testserver",
                    ) as client:
                        response = await client.get("/api/v1/models")
            finally:
                clear_browser_catalog()

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertIsNotNone(payload["last_checked"])
        self.assertTrue(any(item["id"] == "kimi-k2" for item in payload["models"]))
        self.assertIsNotNone(repository.get_model_catalog_snapshot())


@pytest.mark.skipif(create_app is None, reason="fastapi.testclient is not installed")
def test_startup_allows_dedicated_profile_dir() -> None:
    with tempfile.TemporaryDirectory() as temp:
        initialize_catalog = AsyncMock(return_value=None)
        with patch("gracekelly.main._initialize_model_catalog_async", initialize_catalog):
            app = create_app(
                Settings(
                    storage_backend="memory",
                    browser_enabled=True,
                    browser_automation_backend="null",
                    browser_profile_dir=temp,
                )
            )

            async def run_lifespan() -> None:
                async with app.router.lifespan_context(app):
                    return None

            asyncio.run(run_lifespan())

    assert initialize_catalog.await_count == 1


@pytest.mark.skipif(create_app is None, reason="fastapi.testclient is not installed")
def test_startup_rejects_default_chrome_profile_dir() -> None:
    initialize_catalog = AsyncMock(return_value=None)
    with patch("gracekelly.main._initialize_model_catalog_async", initialize_catalog):
        app = create_app(
            Settings(
                storage_backend="memory",
                browser_enabled=True,
                browser_automation_backend="null",
                browser_profile_dir=r"C:\Users\alice\AppData\Local\Google\Chrome\User Data\Default",
            )
        )

        async def run_lifespan() -> None:
            async with app.router.lifespan_context(app):
                return None

        with pytest.raises(RuntimeError) as excinfo:
            asyncio.run(run_lifespan())

    assert "BROWSER_PROFILE_DIR points to a live Chrome profile" in str(excinfo.value)
    assert "python scripts/bootstrap_chrome_profile.py" in str(excinfo.value)
    assert initialize_catalog.await_count == 0


@pytest.mark.skipif(create_app is None, reason="fastapi.testclient is not installed")
def test_startup_rejects_locked_profile_dir() -> None:
    with tempfile.TemporaryDirectory() as temp:
        (Path(temp) / "SingletonLock").write_text("")
        initialize_catalog = AsyncMock(return_value=None)
        with patch("gracekelly.main._initialize_model_catalog_async", initialize_catalog):
            app = create_app(
                Settings(
                    storage_backend="memory",
                    browser_enabled=True,
                    browser_automation_backend="null",
                    browser_profile_dir=temp,
                )
            )

            async def run_lifespan() -> None:
                async with app.router.lifespan_context(app):
                    return None

            with pytest.raises(RuntimeError) as excinfo:
                asyncio.run(run_lifespan())

    assert "BROWSER_PROFILE_DIR points to a live Chrome profile" in str(excinfo.value)
    assert "python scripts/bootstrap_chrome_profile.py" in str(excinfo.value)
    assert initialize_catalog.await_count == 0


@pytest.mark.skipif(create_app is None, reason="fastapi.testclient is not installed")
def test_startup_skips_profile_validation_when_browser_disabled() -> None:
    with tempfile.TemporaryDirectory() as temp:
        (Path(temp) / "SingletonLock").write_text("")
        initialize_catalog = AsyncMock(return_value=None)
        with patch("gracekelly.main._initialize_model_catalog_async", initialize_catalog):
            app = create_app(
                Settings(
                    storage_backend="memory",
                    browser_enabled=False,
                    browser_automation_backend="null",
                    browser_profile_dir=temp,
                )
            )

            async def run_lifespan() -> None:
                async with app.router.lifespan_context(app):
                    return None

            asyncio.run(run_lifespan())

    assert initialize_catalog.await_count == 1


@pytest.mark.skipif(create_app is None, reason="fastapi.testclient is not installed")
def test_create_app_emits_info_logs_when_env_requests_info(
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    from gracekelly.core.models import clear_browser_catalog

    monkeypatch.setenv("GRACEKELLY_LOG_LEVEL", "INFO")
    monkeypatch.setenv("GRACEKELLY_BROWSER_ENABLED", "true")
    caplog.handler.setLevel(logging.INFO)
    clear_browser_catalog()
    try:
        with patch("gracekelly.main._catalog_refresh_adapter", return_value=object()), patch(
            "gracekelly.main._refresh_model_catalog_labels",
            return_value=("Best", "Kimi K2"),
        ):
            app = create_app(Settings.from_env())

            async def run_lifespan() -> None:
                async with app.router.lifespan_context(app):
                    return None

            asyncio.run(run_lifespan())
    finally:
        clear_browser_catalog()

    assert any(
        record.name == "gracekelly.main" and "model_catalog.ready" in record.getMessage()
        for record in caplog.records
    )


@pytest.mark.skipif(create_app is None, reason="fastapi.testclient is not installed")
def test_create_app_hides_info_logs_when_env_requests_warning(
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    from gracekelly.core.models import clear_browser_catalog

    monkeypatch.setenv("GRACEKELLY_LOG_LEVEL", "WARNING")
    monkeypatch.setenv("GRACEKELLY_BROWSER_ENABLED", "true")
    caplog.handler.setLevel(logging.INFO)
    clear_browser_catalog()
    try:
        with patch("gracekelly.main._catalog_refresh_adapter", return_value=object()), patch(
            "gracekelly.main._refresh_model_catalog_labels",
            return_value=("Best", "Kimi K2"),
        ):
            app = create_app(Settings.from_env())

            async def run_lifespan() -> None:
                async with app.router.lifespan_context(app):
                    return None

            asyncio.run(run_lifespan())
    finally:
        clear_browser_catalog()

    assert not any(
        record.name == "gracekelly.main" and "model_catalog.ready" in record.getMessage()
        for record in caplog.records
    )


@pytest.mark.skipif(create_app is None, reason="fastapi.testclient is not installed")
def test_create_app_does_not_duplicate_stream_handler() -> None:
    grace_logger = logging.getLogger("gracekelly")
    root_logger = logging.getLogger()
    original_grace_handlers = list(grace_logger.handlers)
    original_root_handlers = list(root_logger.handlers)
    original_level = grace_logger.level
    try:
        for handler in list(grace_logger.handlers):
            grace_logger.removeHandler(handler)
        for handler in list(root_logger.handlers):
            root_logger.removeHandler(handler)
        create_app(Settings(storage_backend="memory", log_level="INFO"))
        create_app(Settings(storage_backend="memory", log_level="INFO"))
        assert len(grace_logger.handlers) == 1
        assert isinstance(grace_logger.handlers[0], logging.StreamHandler)
    finally:
        for handler in list(grace_logger.handlers):
            grace_logger.removeHandler(handler)
        for handler in original_grace_handlers:
            grace_logger.addHandler(handler)
        for handler in list(root_logger.handlers):
            root_logger.removeHandler(handler)
        for handler in original_root_handlers:
            root_logger.addHandler(handler)
        grace_logger.setLevel(original_level)


if __name__ == "__main__":
    unittest.main()
