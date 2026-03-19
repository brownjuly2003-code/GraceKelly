from __future__ import annotations

from contextlib import asynccontextmanager
import inspect
import logging

from fastapi import FastAPI

from gracekelly.adapters.api.anthropic import AnthropicApiAdapter
from gracekelly.adapters.api.mistral import MistralApiAdapter
from gracekelly.adapters.api.openai_compat import OpenAICompatibleApiAdapter
from gracekelly.adapters.browser.automation import NullBrowserAutomation
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
from gracekelly.api.routes.health import router as health_router
from gracekelly.api.routes.models import router as models_router
from gracekelly.api.routes.orchestrate import router as orchestrate_router
from gracekelly.config import Settings, settings
from gracekelly.core.circuit_breaker import CircuitBreakerConfig, CircuitBreakingExecutionAdapter
from gracekelly.middleware import setup_api_key_auth, setup_rate_limiting, setup_request_metrics
from gracekelly.request_metrics import RequestMetrics
from gracekelly.core.execution_profile import resolve_execution_profile
from gracekelly.core.orchestrator import OrchestratorService
from gracekelly.core.router import ExecutionRouter
from gracekelly.storage.memory import InMemoryTaskRepository

logger = logging.getLogger(__name__)


def build_task_repository(active_settings: Settings):
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


def build_browser_automation(active_settings: Settings):
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


def build_browser_adapter(active_settings: Settings):
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
async def app_lifespan(app: FastAPI):
    yield
    logger.info("Shutting down — releasing resources")
    browser_adapter = getattr(app.state, "browser_adapter", None)
    if browser_adapter is not None:
        close_method = getattr(browser_adapter, "close", None)
        if callable(close_method):
            result = close_method()
            if inspect.isawaitable(result):
                await result
    pool = getattr(app.state, "postgres_pool", None)
    if pool is not None:
        close_method = getattr(pool, "close", None)
        if callable(close_method):
            close_method()
            logger.info("PostgreSQL connection pool closed")


def create_app(app_settings: Settings | None = None) -> FastAPI:
    active_settings = app_settings or settings

    app = FastAPI(
        title="GraceKelly",
        description="Independent orchestrator rebuilt from a clean slate.",
        version="0.1.0",
        lifespan=app_lifespan,
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
    app.state.adapter_registry = {
        "dry-run": app.state.dry_run_adapter,
        "api.mistral": app.state.api_adapters["mistral"],
        "api.openai": app.state.api_adapters["openai"],
        "browser.perplexity": app.state.browser_adapter,
    }
    app.state.execution_router = ExecutionRouter(
        dry_run_adapter=app.state.dry_run_adapter,
        api_adapters=app.state.api_adapters,
        browser_adapter=app.state.browser_adapter,
    )
    app.state.orchestrator_service = OrchestratorService(
        app.state.task_repository,
        execution_router=app.state.execution_router,
    )

    app.state.request_metrics = RequestMetrics()
    setup_api_key_auth(app, api_key=active_settings.api_key)
    setup_rate_limiting(app, requests_per_minute=active_settings.rate_limit_per_minute)
    setup_request_metrics(app)

    app.include_router(health_router)
    app.include_router(models_router)
    app.include_router(orchestrate_router)
    return app


app = create_app()


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("gracekelly.main:app", host=settings.host, port=settings.port, reload=False)
