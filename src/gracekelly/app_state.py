from __future__ import annotations

from typing import TYPE_CHECKING, Any, cast

if TYPE_CHECKING:
    from fastapi import Request

    from gracekelly.config import Settings
    from gracekelly.core.account_pool_manager import AccountPoolManager
    from gracekelly.core.embeddings import EmbeddingsClient
    from gracekelly.core.execution_history import ExecutionHistory
    from gracekelly.core.execution_profile import ExecutionProfile
    from gracekelly.core.orchestrator import OrchestratorService
    from gracekelly.core.router import ExecutionRouter
    from gracekelly.request_metrics import RequestMetrics
    from gracekelly.storage.base import TaskRepository


class AppState:
    settings: Settings
    execution_profile: ExecutionProfile
    task_repository: TaskRepository | None  # None in minimal test apps
    postgres_pool: Any  # None when using InMemoryTaskRepository
    dry_run_adapter: Any
    api_adapters: dict[str, Any]
    browser_adapter: Any
    browser_session_manager: Any  # None when browser is not configured
    adapter_registry: dict[str, Any]
    execution_router: ExecutionRouter
    orchestrator_service: OrchestratorService
    request_metrics: RequestMetrics
    embeddings_client: EmbeddingsClient | None  # None when MISTRAL_API_KEY unset
    execution_history: ExecutionHistory
    account_pool_manager: AccountPoolManager


def get_app_state(request: Request) -> AppState:
    return cast(AppState, request.app.state)
