from __future__ import annotations

from collections.abc import Callable, Iterator
from datetime import UTC, datetime
from typing import Any
from unittest.mock import MagicMock

import pytest
from fastapi import FastAPI

from gracekelly.adapters.browser.perplexity import PerplexityBrowserAdapter
from gracekelly.adapters.browser.policy import ModelVerificationPolicy
from gracekelly.adapters.browser.session import BrowserSessionConfig, BrowserSessionManager
from gracekelly.core.contracts import (
    AdapterHint,
    CancellationToken,
    ExecutionBackend,
    ExecutionMode,
    ExecutionPlan,
    ExecutionRequest,
    ExecutionResult,
    ExecutionStep,
    FileAttachment,
    MergeStrategy,
    StepStatus,
)
from gracekelly.core.models import (
    ModelSpec,
    build_browser_catalog,
    clear_browser_catalog,
    install_browser_catalog,
    resolve_model,
)
from gracekelly.middleware import setup_api_key_auth, setup_security_headers
from gracekelly.schemas import OrchestrateRequest

_TEST_BROWSER_CATALOG_SNAPSHOT = build_browser_catalog(
    (
        "Best",
        "Sonar",
        "Claude Sonnet 4.6",
        "GPT-5.4",
        "Gemini 3.1 Pro",
        "Kimi K2.5",
        "Claude Opus 4.6",
        "Max",
        "Nemotron 3 Super",
    ),
    checked_at=datetime(2026, 4, 20, 12, 0, tzinfo=UTC),
    source="test-fixture",
)


@pytest.fixture(autouse=True)
def install_default_browser_catalog() -> Iterator[None]:
    install_browser_catalog(_TEST_BROWSER_CATALOG_SNAPSHOT)
    yield
    clear_browser_catalog()


@pytest.fixture
def api_model_spec() -> ModelSpec:
    return resolve_model("mistral-small")


@pytest.fixture
def browser_model_spec(install_default_browser_catalog: None) -> ModelSpec:
    return resolve_model("Kimi K2")


@pytest.fixture
def make_execution_step(api_model_spec: ModelSpec) -> Callable[..., ExecutionStep]:
    def _make_execution_step(
        *,
        model: ModelSpec | None = None,
        backend: ExecutionBackend | None = None,
        provider: str | None = None,
        provider_model_id: str | None = None,
        step_index: int = 1,
    ) -> ExecutionStep:
        selected_model = model or api_model_spec
        selected_backend = backend
        if selected_backend is None:
            selected_backend = (
                ExecutionBackend.BROWSER
                if selected_model.adapter_kind == "browser"
                else ExecutionBackend.API
            )
        return ExecutionStep(
            model=selected_model,
            backend=selected_backend,
            provider=provider or selected_model.provider,
            provider_model_id=provider_model_id or selected_model.provider_model_id,
            step_index=step_index,
        )

    return _make_execution_step


@pytest.fixture
def make_execution_plan(
    make_execution_step: Callable[..., ExecutionStep],
) -> Callable[..., ExecutionPlan]:
    def _make_execution_plan(
        *,
        steps: tuple[ExecutionStep, ...] | None = None,
        quorum: int = 1,
        merge_strategy: MergeStrategy = MergeStrategy.FIRST_SUCCESS,
        dry_run: bool = False,
        adapter_hint: AdapterHint = AdapterHint.AUTO,
        cancel_on_quorum: bool = False,
    ) -> ExecutionPlan:
        plan_steps = steps or (make_execution_step(),)
        return ExecutionPlan(
            steps=plan_steps,
            quorum=quorum,
            merge_strategy=merge_strategy,
            dry_run=dry_run,
            adapter_hint=adapter_hint,
            cancel_on_quorum=cancel_on_quorum,
        )

    return _make_execution_plan


@pytest.fixture
def make_execution_request(
    make_execution_plan: Callable[..., ExecutionPlan],
) -> Callable[..., ExecutionRequest]:
    def _make_execution_request(
        *,
        task_id: str = "t1",
        prompt: str = "hello",
        plan: ExecutionPlan | None = None,
        step: ExecutionStep | None = None,
        reasoning: bool = False,
        metadata: dict[str, Any] | None = None,
        cancellation: CancellationToken | None = None,
        attachments: tuple[FileAttachment, ...] = (),
    ) -> ExecutionRequest:
        selected_plan = plan
        selected_step = step
        if selected_plan is None and selected_step is None:
            selected_plan = make_execution_plan()
            selected_step = selected_plan.steps[0]
        elif selected_plan is None:
            selected_plan = make_execution_plan(steps=(selected_step,))
        elif selected_step is None:
            selected_step = selected_plan.steps[0]
        assert selected_step is not None
        return ExecutionRequest(
            task_id=task_id,
            prompt=prompt,
            plan=selected_plan,
            step=selected_step,
            reasoning=reasoning,
            metadata=dict(metadata or {}),
            cancellation=cancellation,
            attachments=attachments,
        )

    return _make_execution_request


@pytest.fixture
def make_execution_result() -> Callable[..., ExecutionResult]:
    def _make_execution_result(
        *,
        adapter_name: str = "api.mistral",
        model_id: str = "mistral-small",
        model_display_name: str = "Mistral Small",
        execution_mode: ExecutionMode = ExecutionMode.API,
        status: StepStatus = StepStatus.COMPLETED,
        output_text: str | None = "ok",
        duration_ms: int | None = None,
        details: dict[str, Any] | None = None,
    ) -> ExecutionResult:
        return ExecutionResult(
            adapter_name=adapter_name,
            model_id=model_id,
            model_display_name=model_display_name,
            execution_mode=execution_mode,
            status=status,
            output_text=output_text,
            duration_ms=duration_ms,
            details=dict(details or {}),
        )

    return _make_execution_result


@pytest.fixture
def make_api_mock_request() -> Callable[..., MagicMock]:
    def _make_api_mock_request(
        *,
        task_id: str = "t1",
        prompt: str = "Hello",
        model_id: str = "m1",
        display_name: str = "M1",
        timeout_seconds: int = 10,
        provider_model_id: str | None = None,
        reasoning: bool = False,
    ) -> MagicMock:
        req = MagicMock()
        req.task_id = task_id
        req.prompt = prompt
        req.reasoning = reasoning
        req.metadata = {}
        req.step.model.id = model_id
        req.step.model.display_name = display_name
        req.step.model.timeout_seconds = timeout_seconds
        req.step.provider_model_id = provider_model_id or model_id
        req.models = (req.step.model,)
        return req

    return _make_api_mock_request


@pytest.fixture
def make_browser_session_manager() -> Callable[..., BrowserSessionManager]:
    def _make_browser_session_manager(
        *,
        enabled: bool = True,
        profile_dir: str | None = "D:\\Profiles\\GraceKelly",
    ) -> BrowserSessionManager:
        return BrowserSessionManager(
            BrowserSessionConfig(
                enabled=enabled,
                provider="perplexity",
                base_url="https://www.perplexity.ai",
                profile_dir=profile_dir,
            )
        )

    return _make_browser_session_manager


@pytest.fixture
def make_browser_request(
    browser_model_spec: ModelSpec,
    make_execution_plan: Callable[..., ExecutionPlan],
    make_execution_step: Callable[..., ExecutionStep],
) -> Callable[..., ExecutionRequest]:
    def _make_browser_request(
        *,
        task_id: str = "task-browser-1",
        prompt: str = "hello",
        cancellation: CancellationToken | None = None,
        attachments: tuple[FileAttachment, ...] = (),
    ) -> ExecutionRequest:
        step = make_execution_step(
            model=browser_model_spec,
            backend=ExecutionBackend.BROWSER,
            step_index=1,
        )
        plan = make_execution_plan(
            steps=(step,),
            quorum=1,
            merge_strategy=MergeStrategy.FIRST_SUCCESS,
            dry_run=False,
            adapter_hint=AdapterHint.AUTO,
            cancel_on_quorum=True,
        )
        return ExecutionRequest(
            task_id=task_id,
            prompt=prompt,
            plan=plan,
            step=step,
            reasoning=False,
            metadata={},
            cancellation=cancellation,
            attachments=attachments,
        )

    return _make_browser_request


@pytest.fixture
def make_browser_adapter(
    make_browser_session_manager: Callable[..., BrowserSessionManager],
) -> Callable[..., PerplexityBrowserAdapter]:
    def _make_browser_adapter(
        *,
        allow_alias_match: bool = True,
    ) -> PerplexityBrowserAdapter:
        return PerplexityBrowserAdapter(
            session_manager=make_browser_session_manager(),
            model_verification_policy=ModelVerificationPolicy(
                allow_alias_match=allow_alias_match,
            ),
        )

    return _make_browser_adapter


@pytest.fixture
def make_security_headers_app() -> Callable[[], FastAPI]:
    def _make_security_headers_app() -> FastAPI:
        app = FastAPI()

        @app.get("/health")
        def health() -> dict[str, str]:
            return {"status": "ok"}

        @app.get("/api/v1/models")
        def models() -> list[dict[str, str]]:
            return []

        setup_security_headers(app)
        return app

    return _make_security_headers_app


@pytest.fixture
def make_api_test_app() -> Callable[..., FastAPI]:
    def _make_api_test_app(
        *,
        api_key: str | None = None,
    ) -> FastAPI:
        app = FastAPI()

        @app.get("/health")
        def health() -> dict[str, str]:
            return {"status": "ok"}

        @app.get("/api/v1/models")
        def models() -> list[dict[str, str]]:
            return []

        @app.post("/api/v1/orchestrate")
        def orchestrate() -> dict[str, str]:
            return {"task_id": "t1"}

        @app.get("/api/v1/readiness")
        def readiness() -> dict[str, str]:
            return {"status": "ok"}

        @app.get("/metrics")
        def metrics() -> str:
            return "metrics"

        setup_api_key_auth(app, api_key=api_key)
        return app

    return _make_api_test_app


@pytest.fixture
def make_orchestrate_request() -> Callable[..., OrchestrateRequest]:
    def _make_orchestrate_request(**overrides: Any) -> OrchestrateRequest:
        data: dict[str, Any] = {"prompt": "Q"}
        if "model" not in overrides and "models" not in overrides:
            data["model"] = "Mistral"
        data.update(overrides)
        return OrchestrateRequest(**data)

    return _make_orchestrate_request


@pytest.fixture
def inject_shared_test_factories(
    request: pytest.FixtureRequest,
    make_api_mock_request: Callable[..., MagicMock],
    make_api_test_app: Callable[..., FastAPI],
    make_browser_adapter: Callable[..., PerplexityBrowserAdapter],
    make_browser_request: Callable[..., ExecutionRequest],
    make_browser_session_manager: Callable[..., BrowserSessionManager],
    make_execution_plan: Callable[..., ExecutionPlan],
    make_execution_request: Callable[..., ExecutionRequest],
    make_execution_result: Callable[..., ExecutionResult],
    make_execution_step: Callable[..., ExecutionStep],
    make_orchestrate_request: Callable[..., OrchestrateRequest],
    make_security_headers_app: Callable[[], FastAPI],
) -> None:
    module_name = request.module.__name__.rsplit(".", maxsplit=1)[-1]
    if module_name == "test_api_adapter_execute":
        request.module._make_request = make_api_mock_request
    if module_name == "test_middleware":
        request.module._test_app = make_api_test_app
        request.module._test_app_with_security_headers = make_security_headers_app
    if module_name == "test_contracts":
        request.module._make_execution_step = make_execution_step
        request.module._make_execution_plan = make_execution_plan
        request.module._make_execution_request = make_execution_request
    if module_name == "test_planning":
        request.module._make_orchestrate_request = make_orchestrate_request

    instance = getattr(request, "instance", None)
    if instance is None:
        return

    if module_name == "test_browser_adapter":
        instance.build_request = make_browser_request
        instance.build_session_manager = make_browser_session_manager
        instance._make_adapter = make_browser_adapter
        instance._session_manager = make_browser_session_manager

    if module_name == "test_contracts":
        instance.make_execution_step = make_execution_step
        instance.make_execution_plan = make_execution_plan
        instance.make_execution_request = make_execution_request
        instance.make_execution_result = make_execution_result

    if module_name == "test_planning":
        instance.make_orchestrate_request = make_orchestrate_request
