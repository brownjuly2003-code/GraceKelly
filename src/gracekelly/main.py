from __future__ import annotations

import inspect
import logging
import pathlib
from collections.abc import AsyncGenerator
from concurrent.futures import ThreadPoolExecutor
from contextlib import asynccontextmanager
from typing import Any

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from starlette.exceptions import HTTPException as StarletteHTTPException

from gracekelly.adapters.api.anthropic import AnthropicApiAdapter
from gracekelly.adapters.api.mistral import MistralApiAdapter
from gracekelly.adapters.api.openai_compat import OpenAICompatibleApiAdapter
from gracekelly.adapters.browser.automation import BrowserAutomationPort, NullBrowserAutomation
from gracekelly.adapters.browser.perplexity import PerplexityBrowserAdapter
from gracekelly.adapters.browser.playwright_driver import PlaywrightBrowserAutomation, PlaywrightBrowserRuntimeConfig
from gracekelly.adapters.browser.policy import (
    AuthRecoveryPolicy,
    ModelVerificationPolicy,
    PopupPolicy,
    SubmitPolicy,
)
from gracekelly.adapters.browser.scripted import ScriptedBrowserAutomation, ScriptedBrowserScenario
from gracekelly.adapters.browser.session import BrowserSessionConfig, BrowserSessionManager
from gracekelly.adapters.dry_run import DryRunExecutionAdapter
from gracekelly.api.routes.analytics import router as analytics_router
from gracekelly.api.routes.batch import router as batch_router
from gracekelly.api.routes.compare import router as compare_router
from gracekelly.api.routes.consensus import router as consensus_router
from gracekelly.api.routes.debate import router as debate_router
from gracekelly.api.routes.health import router as health_router
from gracekelly.api.routes.health_detailed import router as health_detailed_router
from gracekelly.api.routes.models import router as models_router
from gracekelly.api.routes.orchestrate import router as orchestrate_router
from gracekelly.api.routes.pipeline import router as pipeline_router
from gracekelly.api.routes.smart import router as smart_router
from gracekelly.api.routes.smart_v2 import router as smart_v2_router
from gracekelly.api.routes.stream import router as stream_router
from gracekelly.config import Settings, settings
from gracekelly.core.account_pool_manager import AccountPoolManager
from gracekelly.core.circuit_breaker import CircuitBreakerConfig, CircuitBreakingExecutionAdapter
from gracekelly.core.contracts import ExecutionAdapter
from gracekelly.core.embeddings import EmbeddingsClient
from gracekelly.core.execution_history import ExecutionHistory
from gracekelly.core.execution_profile import resolve_execution_profile
from gracekelly.core.orchestrator import OrchestratorService
from gracekelly.core.router import ExecutionRouter
from gracekelly.middleware import (
    setup_api_key_auth,
    setup_correlation_id,
    setup_rate_limiting,
    setup_request_metrics,
    setup_security_headers,
    setup_sentry,
)
from gracekelly.request_metrics import RequestMetrics
from gracekelly.storage.base import TaskRepository
from gracekelly.storage.memory import InMemoryTaskRepository
from gracekelly.telemetry import setup_telemetry

logger = logging.getLogger(__name__)


def _get_version() -> str:
    try:
        from importlib.metadata import version as _v

        return _v("gracekelly")
    except Exception:
        return "0.0.0-dev"


def build_task_repository(active_settings: Settings) -> TaskRepository:
    storage_backend = active_settings.storage_backend
    if storage_backend == "memory":
        return InMemoryTaskRepository()
    if storage_backend == "postgres":
        if not active_settings.postgres_dsn:
            raise ValueError("GRACEKELLY_POSTGRES_DSN is required for the postgres backend.")
        from gracekelly.storage.postgres import PostgresTaskRepository

        return PostgresTaskRepository(
            active_settings.postgres_dsn,
            bootstrap=True,
            connect_timeout_seconds=active_settings.postgres_connect_timeout_seconds,
            use_pool=active_settings.postgres_pool_enabled,
            pool_min_size=active_settings.postgres_pool_min_size,
            pool_max_size=active_settings.postgres_pool_max_size,
        )
    raise ValueError(f"Unsupported storage backend: {storage_backend}")


def build_browser_automation(active_settings: Settings) -> BrowserAutomationPort:
    backend = active_settings.browser_automation_backend
    if backend == "null":
        return NullBrowserAutomation()
    if backend == "playwright":
        return PlaywrightBrowserAutomation(
            runtime=PlaywrightBrowserRuntimeConfig(
                channel=active_settings.browser_playwright_channel,
                headless=active_settings.browser_playwright_headless,
            )
        )
    if backend == "scripted":
        return ScriptedBrowserAutomation(
            ScriptedBrowserScenario(
                logged_in=active_settings.browser_scripted_logged_in,
                actual_model_label=active_settings.browser_scripted_model_label,
                output_text=active_settings.browser_scripted_output_text,
            )
        )
    raise ValueError(f"Unsupported browser automation backend: {backend}")


def build_browser_adapter(active_settings: Settings) -> ExecutionAdapter:
    adapter = PerplexityBrowserAdapter(
        session_manager=BrowserSessionManager(
            BrowserSessionConfig(
                enabled=active_settings.browser_enabled,
                provider="perplexity",
                base_url=active_settings.browser_base_url,
                profile_dir=active_settings.browser_profile_dir,
            )
        ),
        automation=build_browser_automation(active_settings),
        popup_policy=PopupPolicy(),
        auth_recovery_policy=AuthRecoveryPolicy(),
        model_verification_policy=ModelVerificationPolicy(),
        submit_policy=SubmitPolicy(),
    )
    return CircuitBreakingExecutionAdapter(
        adapter,
        config=CircuitBreakerConfig(
            enabled=active_settings.browser_circuit_breaker_enabled,
            failure_threshold=active_settings.browser_circuit_breaker_failure_threshold,
            cooldown_seconds=active_settings.browser_circuit_breaker_cooldown_seconds,
        ),
    )


@asynccontextmanager
async def app_lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    yield
    logger.info("Shutting down — releasing resources")
    browser_adapter = getattr(app.state, "browser_adapter", None)
    if browser_adapter is not None:
        close_method = getattr(browser_adapter, "close", None)
        if callable(close_method):
            result = close_method()
            if inspect.isawaitable(result):
                await result
    execution_executor = getattr(app.state, "execution_executor", None)
    if execution_executor is not None:
        execution_executor.shutdown(wait=False)
    browser_executor = getattr(app.state, "browser_executor", None)
    if browser_executor is not None and browser_executor is not execution_executor:
        browser_executor.shutdown(wait=False)
    pool = getattr(app.state, "postgres_pool", None)
    if pool is not None:
        close_method = getattr(pool, "close", None)
        if callable(close_method):
            close_method()
            logger.info("PostgreSQL connection pool closed")


def create_app(app_settings: Settings | None = None) -> FastAPI:
    active_settings = app_settings or settings
    active_settings.validate()

    app = FastAPI(
        title="GraceKelly",
        description="Independent orchestrator rebuilt from a clean slate.",
        version=_get_version(),
        lifespan=app_lifespan,
    )
    setup_telemetry(app, active_settings.otel_endpoint, active_settings.otel_service_name)

    @app.exception_handler(StarletteHTTPException)
    async def http_exception_handler(request: Request, exc: StarletteHTTPException) -> JSONResponse:
        return JSONResponse(
            status_code=exc.status_code,
            content={
                "type": f"https://httpstatuses.com/{exc.status_code}",
                "title": exc.detail if isinstance(exc.detail, str) else "HTTP Error",
                "status": exc.status_code,
                "detail": exc.detail,
            },
        )

    @app.exception_handler(RequestValidationError)
    async def validation_exception_handler(request: Request, exc: RequestValidationError) -> JSONResponse:
        errors = exc.errors()
        detail = "; ".join(f"{'.'.join(str(loc) for loc in error['loc'])}: {error['msg']}" for error in errors)
        return JSONResponse(
            status_code=422,
            content={
                "type": "https://httpstatuses.com/422",
                "title": "Validation Error",
                "status": 422,
                "detail": detail,
            },
        )

    app.state.settings = active_settings
    app.state.execution_profile = resolve_execution_profile(active_settings.execution_profile)
    app.state.task_repository = build_task_repository(active_settings)
    app.state.postgres_pool = getattr(app.state.task_repository, "_pool", None)
    app.state.dry_run_adapter = DryRunExecutionAdapter()
    app.state.api_adapters = {
        "mistral": MistralApiAdapter(
            api_key=active_settings.mistral_api_key,
            base_url=active_settings.mistral_base_url,
            timeout_seconds=active_settings.mistral_timeout_seconds,
            max_retries=active_settings.mistral_max_retries,
            retry_backoff_seconds=active_settings.mistral_retry_backoff_seconds,
        ),
        "openai": OpenAICompatibleApiAdapter(
            api_key=active_settings.openai_api_key,
            base_url=active_settings.openai_base_url,
            timeout_seconds=active_settings.openai_timeout_seconds,
            max_retries=active_settings.openai_max_retries,
            retry_backoff_seconds=active_settings.openai_retry_backoff_seconds,
        ),
        "anthropic": AnthropicApiAdapter(
            api_key=active_settings.anthropic_api_key,
            base_url=active_settings.anthropic_base_url,
            timeout_seconds=active_settings.anthropic_timeout_seconds,
            max_retries=active_settings.anthropic_max_retries,
            retry_backoff_seconds=active_settings.anthropic_retry_backoff_seconds,
        ),
    }
    app.state.browser_adapter = build_browser_adapter(active_settings)
    app.state.browser_session_manager = getattr(app.state.browser_adapter, "session_manager", None)
    app.state.browser_executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="browser")
    app.state.execution_executor = ThreadPoolExecutor(
        max_workers=max(1, len(app.state.api_adapters) + int(app.state.browser_adapter is not None)),
        thread_name_prefix="execution",
    )
    app.state.adapter_registry = {
        "dry-run": app.state.dry_run_adapter,
        "api.mistral": app.state.api_adapters["mistral"],
        "api.openai": app.state.api_adapters["openai"],
        "api.anthropic": app.state.api_adapters["anthropic"],
        "browser.perplexity": app.state.browser_adapter,
    }
    app.state.execution_router = ExecutionRouter(
        dry_run_adapter=app.state.dry_run_adapter,
        api_adapters=app.state.api_adapters,
        browser_adapter=app.state.browser_adapter,
        executor=app.state.execution_executor,
    )
    app.state.orchestrator_service = OrchestratorService(
        app.state.task_repository,
        execution_router=app.state.execution_router,
        settings=active_settings,
    )

    app.state.request_metrics = RequestMetrics()
    _mistral_key = active_settings.mistral_api_key
    app.state.embeddings_client = (
        EmbeddingsClient(api_key=_mistral_key, base_url="https://api.mistral.ai/v1")
        if _mistral_key
        else None
    )
    app.state.execution_history = ExecutionHistory()
    app.state.account_pool_manager = AccountPoolManager()

    setup_sentry(active_settings.sentry_dsn, active_settings.sentry_environment)
    setup_security_headers(app)
    setup_api_key_auth(app, api_key=active_settings.api_key)
    setup_request_metrics(app)
    setup_correlation_id(app)
    setup_rate_limiting(
        app,
        active_settings.redis_url,
        active_settings.rate_limit_rpm,
        active_settings.rate_limit_burst,
    )

    app.include_router(health_router)
    app.include_router(models_router)
    app.include_router(orchestrate_router)
    app.include_router(stream_router)
    app.include_router(consensus_router)
    app.include_router(analytics_router)
    app.include_router(smart_router)
    app.include_router(batch_router)
    app.include_router(pipeline_router)
    app.include_router(health_detailed_router)
    app.include_router(smart_v2_router)
    app.include_router(debate_router)
    app.include_router(compare_router)
    _static_dir = pathlib.Path(__file__).parent.parent.parent / "static"
    if _static_dir.exists():
        app.mount("/", StaticFiles(directory=str(_static_dir), html=True), name="static")
        _static_mount = app.router.routes[-1]
        _add_api_route = app.router.add_api_route

        def add_api_route(path: str, endpoint: Any, **kwargs: Any) -> None:
            _add_api_route(path, endpoint, **kwargs)
            if _static_mount in app.router.routes and app.router.routes[-1] is not _static_mount:
                app.router.routes.remove(_static_mount)
                app.router.routes.append(_static_mount)

        app.router.add_api_route = add_api_route  # type: ignore[method-assign]
    return app


def app_factory() -> FastAPI:
    return create_app()


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("gracekelly.main:app_factory", host=settings.host, port=settings.port, reload=False, factory=True)
