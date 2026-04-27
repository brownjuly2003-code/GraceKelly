from __future__ import annotations

from datetime import UTC, datetime, timedelta
from unittest.mock import patch

from fastapi.testclient import TestClient

from gracekelly.adapters.browser.automation import BrowserAuthStatus
from gracekelly.config import Settings
from gracekelly.core.contracts import ExecutionAdapter, ExecutionRequest, ExecutionResult
from gracekelly.core.models import build_browser_catalog, clear_browser_catalog, resolve_model
from gracekelly.main import create_app
from gracekelly.storage.memory import InMemoryTaskRepository


class _FakeCatalogBrowserAdapter(ExecutionAdapter):
    name = "browser.perplexity"

    def __init__(
        self,
        *,
        labels: tuple[str, ...] | None = None,
        error: Exception | None = None,
    ) -> None:
        self._labels = labels or ()
        self._error = error

    def execute(self, request: ExecutionRequest) -> ExecutionResult:
        raise NotImplementedError

    def refresh_model_catalog(self) -> tuple[str, ...]:
        if self._error is not None:
            raise self._error
        return self._labels

    def healthcheck(self) -> dict[str, object]:
        return {
            "status": "ok",
            "adapter_name": self.name,
        }


class _NonRefreshingBrowserAdapter(ExecutionAdapter):
    name = "browser.perplexity"

    def execute(self, request: ExecutionRequest) -> ExecutionResult:
        raise NotImplementedError

    def healthcheck(self) -> dict[str, object]:
        return {
            "status": "ok",
            "adapter_name": self.name,
        }


class _FakePlaywrightCatalogAutomation:
    def __init__(self) -> None:
        self.closed = False

    def ensure_session(self, session_manager: object) -> None:
        return None

    def dismiss_popups(self, policy: object) -> None:
        return None

    def auth_status(self, policy: object) -> BrowserAuthStatus:
        return BrowserAuthStatus(logged_in=True)

    def recover_auth(self, policy: object) -> BrowserAuthStatus:
        return BrowserAuthStatus(logged_in=True)

    def inspect_model_catalog(self) -> tuple[str, ...]:
        return ("Best", "Sonar", "Claude Sonnet 4.6")

    def close(self) -> None:
        self.closed = True

    def healthcheck(self) -> dict[str, object]:
        return {
            "status": "ok",
            "implemented": True,
            "driver": "playwright-fake",
        }


def _settings() -> Settings:
    return Settings(
        storage_backend="memory",
        browser_enabled=True,
        browser_automation_backend="null",
    )


def test_default_dry_run_no_browser_models_route_returns_static_catalog() -> None:
    clear_browser_catalog()
    repository = InMemoryTaskRepository()

    with patch("gracekelly.main.build_task_repository", return_value=repository):
        app = create_app(
            Settings(
                storage_backend="memory",
                execution_profile="dry-run",
                browser_enabled=False,
            )
        )
        with TestClient(app) as client:
            response = client.get("/api/v1/models")

    assert response.status_code == 200
    payload = response.json()
    assert payload["source"] == "dry-run-static"
    ids = {item["id"] for item in payload["models"]}
    assert "sonar" in ids
    assert "gpt-5-4-api" in ids
    sonar = next(item for item in payload["models"] if item["id"] == "sonar")
    assert sonar["availability_status"] == "unknown"
    assert sonar["availability_source"] == "dry-run-static"


def test_startup_refreshes_missing_browser_catalog_and_installs_runtime_registry() -> None:
    clear_browser_catalog()
    repository = InMemoryTaskRepository()
    browser_adapter = _FakeCatalogBrowserAdapter(labels=("Best", "DeepSeek R1"))

    with patch("gracekelly.main.build_task_repository", return_value=repository), patch(
        "gracekelly.main.build_browser_adapter",
        return_value=browser_adapter,
    ):
        app = create_app(_settings())
        with TestClient(app) as client:
            response = client.get("/api/v1/models")

    assert response.status_code == 200
    payload = response.json()
    assert payload["last_checked"] is not None
    assert any(item["id"] == "deepseek-r1" for item in payload["models"])
    assert resolve_model("DeepSeek R1").id == "deepseek-r1"
    snapshot = repository.get_model_catalog_snapshot()
    assert snapshot is not None
    assert any(model.id == "deepseek-r1" for model in snapshot.models)


def test_models_route_returns_last_snapshot_when_refresh_fails() -> None:
    clear_browser_catalog()
    repository = InMemoryTaskRepository()
    browser_adapter = _FakeCatalogBrowserAdapter(error=RuntimeError("perplexity unavailable"))

    stale_checked_at = datetime.now(UTC) - timedelta(hours=30)
    repository.save_model_catalog_snapshot(
        build_browser_catalog(
            ("Best", "GPT-5.4"),
            checked_at=stale_checked_at,
            source="perplexity-model-menu",
        )
    )

    with patch("gracekelly.main.build_task_repository", return_value=repository), patch(
        "gracekelly.main.build_browser_adapter",
        return_value=browser_adapter,
    ):
        app = create_app(_settings())
        with TestClient(app) as client:
            response = client.get("/api/v1/models")

    assert response.status_code == 200
    payload = response.json()
    assert datetime.fromisoformat(payload["last_checked"].replace("Z", "+00:00")) == stale_checked_at
    assert any(item["id"] == "gpt-5-4" for item in payload["models"])


def test_models_route_returns_503_without_snapshot_and_failed_refresh() -> None:
    clear_browser_catalog()
    repository = InMemoryTaskRepository()
    browser_adapter = _FakeCatalogBrowserAdapter(error=RuntimeError("perplexity unavailable"))

    with patch("gracekelly.main.build_task_repository", return_value=repository), patch(
        "gracekelly.main.build_browser_adapter",
        return_value=browser_adapter,
    ):
        app = create_app(_settings())
        with TestClient(app) as client:
            response = client.get("/api/v1/models")

    assert response.status_code == 503


def test_startup_refresh_uses_dedicated_playwright_catalog_refresh_when_execution_adapter_cannot_refresh() -> None:
    clear_browser_catalog()
    repository = InMemoryTaskRepository()
    browser_adapter = _NonRefreshingBrowserAdapter()
    automation = _FakePlaywrightCatalogAutomation()

    with patch("gracekelly.main.build_task_repository", return_value=repository), patch(
        "gracekelly.main.build_browser_adapter",
        return_value=browser_adapter,
    ), patch(
        "gracekelly.main.PlaywrightBrowserAutomation",
        return_value=automation,
    ):
        app = create_app(
            Settings(
                storage_backend="memory",
                browser_enabled=True,
                browser_automation_backend="null",
                browser_profile_dir=r"D:\Profiles\GraceKelly",
            )
        )
        with TestClient(app) as client:
            response = client.get("/api/v1/models")

    assert response.status_code == 200
    payload = response.json()
    assert payload["last_checked"] is not None
    assert any(item["id"] == "sonar" for item in payload["models"])
    assert repository.get_model_catalog_snapshot() is not None
    assert automation.closed is True
