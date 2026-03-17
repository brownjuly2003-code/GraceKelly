from __future__ import annotations

from fastapi import FastAPI

from gracekelly.adapters.api.mistral import MistralApiAdapter
from gracekelly.adapters.browser.automation import NullBrowserAutomation
from gracekelly.adapters.browser.perplexity import PerplexityBrowserAdapter
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
from gracekelly.core.execution_profile import resolve_execution_profile
from gracekelly.core.orchestrator import OrchestratorService
from gracekelly.core.router import ExecutionRouter
from gracekelly.storage.memory import InMemoryTaskRepository


def build_task_repository(active_settings: Settings):
    storage_backend = active_settings.storage_backend
    if storage_backend == "memory":
        return InMemoryTaskRepository()
    if storage_backend == "postgres":
        if not active_settings.postgres_dsn:
            raise ValueError("GRACEKELLY_POSTGRES_DSN is required for the postgres backend.")
        from gracekelly.storage.postgres import PostgresTaskRepository

        return PostgresTaskRepository(active_settings.postgres_dsn, bootstrap=True)
    raise ValueError(f"Unsupported storage backend: {storage_backend}")


def build_browser_automation(active_settings: Settings):
    backend = active_settings.browser_automation_backend
    if backend == "null":
        return NullBrowserAutomation()
    if backend == "scripted":
        return ScriptedBrowserAutomation(
            ScriptedBrowserScenario(
                logged_in=active_settings.browser_scripted_logged_in,
                actual_model_label=active_settings.browser_scripted_model_label,
                output_text=active_settings.browser_scripted_output_text,
            )
        )
    raise ValueError(f"Unsupported browser automation backend: {backend}")


def create_app(app_settings: Settings | None = None) -> FastAPI:
    active_settings = app_settings or settings

    app = FastAPI(
        title="GraceKelly",
        description="Independent orchestrator rebuilt from a clean slate.",
        version="0.1.0",
    )
    app.state.settings = active_settings
    app.state.execution_profile = resolve_execution_profile(active_settings.execution_profile)
    app.state.task_repository = build_task_repository(active_settings)
    app.state.dry_run_adapter = DryRunExecutionAdapter()
    app.state.api_adapters = {
        "mistral": MistralApiAdapter(
            api_key=active_settings.mistral_api_key,
            base_url=active_settings.mistral_base_url,
            timeout_seconds=active_settings.mistral_timeout_seconds,
        )
    }
    app.state.browser_session_manager = BrowserSessionManager(
        BrowserSessionConfig(
            enabled=active_settings.browser_enabled,
            provider="perplexity",
            base_url=active_settings.browser_base_url,
            profile_dir=active_settings.browser_profile_dir,
        )
    )
    app.state.browser_adapter = PerplexityBrowserAdapter(
        session_manager=app.state.browser_session_manager,
        automation=build_browser_automation(active_settings),
        popup_policy=PopupPolicy(),
        auth_recovery_policy=AuthRecoveryPolicy(),
        model_verification_policy=ModelVerificationPolicy(),
        submit_policy=SubmitPolicy(),
    )
    app.state.adapter_registry = {
        "dry-run": app.state.dry_run_adapter,
        "api.mistral": app.state.api_adapters["mistral"],
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

    app.include_router(health_router)
    app.include_router(models_router)
    app.include_router(orchestrate_router)
    return app


app = create_app()


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("gracekelly.main:app", host=settings.host, port=settings.port, reload=False)
