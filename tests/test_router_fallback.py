from __future__ import annotations

import logging
import unittest
from dataclasses import asdict, replace
from unittest.mock import patch

import pytest

from gracekelly.config import Settings
from gracekelly.config import settings as _default_settings
from gracekelly.core.contracts import (
    AdapterHint,
    ExecutionAdapter,
    ExecutionBackend,
    ExecutionMode,
    ExecutionPlan,
    ExecutionRequest,
    ExecutionResult,
    ExecutionStep,
    FailureCode,
    MergeStrategy,
    StepStatus,
    TaskStatus,
)
from gracekelly.core.models import ModelSpec, build_browser_model_spec, deserialize_model_spec
from gracekelly.core.router import ExecutionRouter


def _make_spec(
    model_id: str,
    *,
    adapter_kind: str,
    provider: str,
    provider_model_id: str | None = None,
    concurrency_limit: int | None = None,
    fallback_model_id: str | None = None,
) -> ModelSpec:
    return ModelSpec(
        id=model_id,
        display_name=model_id,
        aliases=(model_id,),
        adapter_kind=adapter_kind,
        provider=provider,
        provider_model_id=provider_model_id or model_id,
        timeout_seconds=60,
        expected_latency_class="slow",
        concurrency_limit=concurrency_limit if concurrency_limit is not None else (1 if adapter_kind == "browser" else 4),
        reasoning_capable=True,
        fallback_model_id=fallback_model_id,
    )


def _make_step(spec: ModelSpec, *, step_index: int = 0) -> ExecutionStep:
    return ExecutionStep(
        model=spec,
        backend=ExecutionBackend(spec.adapter_kind),
        provider=spec.provider,
        provider_model_id=spec.provider_model_id,
        step_index=step_index,
    )


def _make_plan(step: ExecutionStep) -> ExecutionPlan:
    return ExecutionPlan(
        steps=(step,),
        quorum=1,
        merge_strategy=MergeStrategy.FIRST_SUCCESS,
        dry_run=False,
        adapter_hint=AdapterHint.AUTO,
        cancel_on_quorum=False,
    )


def _result(
    step: ExecutionStep,
    *,
    status: StepStatus,
    failure_code: FailureCode | None = None,
    failure_message: str | None = None,
    output_text: str | None = None,
) -> ExecutionResult:
    return ExecutionResult(
        adapter_name=f"{step.backend.value}.{step.provider}",
        model_id=step.model.id,
        model_display_name=step.model.display_name,
        execution_mode=ExecutionMode(step.backend.value),
        status=status,
        failure_code=failure_code,
        failure_message=failure_message,
        output_text=output_text,
    )


class _FakeAdapter(ExecutionAdapter):
    name = "fake"

    def __init__(self, results: list[ExecutionResult]) -> None:
        self._results = list(results)
        self.calls: list[str] = []

    def execute(self, request: ExecutionRequest) -> ExecutionResult:
        self.calls.append(request.step.model.id)
        return self._results.pop(0)


class RouterFallbackTests(unittest.TestCase):
    def test_fallback_disabled_by_default_even_with_fallback_id(self) -> None:
        primary = _make_spec(
            "claude-sonnet-4-6",
            adapter_kind="browser",
            provider="perplexity",
            provider_model_id="Claude Sonnet 4.6",
            fallback_model_id="claude-sonnet-4-6-api",
        )
        fallback = _make_spec(
            "claude-sonnet-4-6-api",
            adapter_kind="api",
            provider="anthropic",
            provider_model_id="claude-sonnet-4-6-20250514",
        )
        step = _make_step(primary)
        browser_adapter = _FakeAdapter([
            _result(
                step,
                status=StepStatus.FAILED,
                failure_code=FailureCode.PROVIDER_UNAVAILABLE,
                failure_message="browser unavailable",
            ),
        ])
        api_adapter = _FakeAdapter([
            _result(_make_step(fallback), status=StepStatus.COMPLETED, output_text="fallback output"),
        ])

        with patch("gracekelly.core.router.list_models", return_value=(primary, fallback)):
            router = ExecutionRouter(
                dry_run_adapter=_FakeAdapter([]),
                api_adapters={"anthropic": api_adapter},
                browser_adapter=browser_adapter,
                settings=Settings(enable_model_fallback=False),
            )
            batch = router.execute(
                task_id="t1",
                prompt="Q",
                plan=_make_plan(step),
                reasoning=False,
                metadata={},
            )

        self.assertEqual(batch.task_status, TaskStatus.FAILED)
        self.assertEqual(batch.failure_code, FailureCode.PROVIDER_UNAVAILABLE)
        self.assertNotIn("fallback_used", batch.results[0].details)
        self.assertEqual(browser_adapter.calls, ["claude-sonnet-4-6"])
        self.assertEqual(api_adapter.calls, [])

    def test_router_uses_injected_settings_for_fallback(self) -> None:
        primary = _make_spec(
            "claude-sonnet-4-6",
            adapter_kind="browser",
            provider="perplexity",
            provider_model_id="Claude Sonnet 4.6",
            fallback_model_id="claude-sonnet-4-6-api",
        )
        fallback = _make_spec(
            "claude-sonnet-4-6-api",
            adapter_kind="api",
            provider="anthropic",
            provider_model_id="claude-sonnet-4-6-20250514",
        )
        step = _make_step(primary)
        browser_adapter = _FakeAdapter([
            _result(
                step,
                status=StepStatus.FAILED,
                failure_code=FailureCode.AUTH_FAILED,
                failure_message="login required",
            ),
        ])
        api_adapter = _FakeAdapter([
            _result(_make_step(fallback), status=StepStatus.COMPLETED, output_text="fallback output"),
        ])

        with patch("gracekelly.core.router.list_models", return_value=(primary, fallback)):
            router = ExecutionRouter(
                dry_run_adapter=_FakeAdapter([]),
                api_adapters={"anthropic": api_adapter},
                browser_adapter=browser_adapter,
                settings=Settings(enable_model_fallback=True),
            )
            batch = router.execute(
                task_id="t1",
                prompt="Q",
                plan=_make_plan(step),
                reasoning=False,
                metadata={},
            )

        self.assertEqual(batch.task_status, TaskStatus.COMPLETED)
        self.assertEqual(batch.results[0].model_id, "claude-sonnet-4-6-api")
        self.assertTrue(batch.results[0].details["fallback_used"])
        self.assertEqual(batch.results[0].details["fallback_reason"], "auth_failed")
        self.assertEqual(browser_adapter.calls, ["claude-sonnet-4-6"])
        self.assertEqual(api_adapter.calls, ["claude-sonnet-4-6-api"])

    def test_fallback_triggers_on_auth_failed_when_enabled(self) -> None:
        primary = _make_spec(
            "claude-sonnet-4-6",
            adapter_kind="browser",
            provider="perplexity",
            provider_model_id="Claude Sonnet 4.6",
            fallback_model_id="claude-sonnet-4-6-api",
        )
        fallback = _make_spec(
            "claude-sonnet-4-6-api",
            adapter_kind="api",
            provider="anthropic",
            provider_model_id="claude-sonnet-4-6-20250514",
        )
        step = _make_step(primary)
        browser_adapter = _FakeAdapter([
            _result(
                step,
                status=StepStatus.FAILED,
                failure_code=FailureCode.AUTH_FAILED,
                failure_message="login required",
            ),
        ])
        api_adapter = _FakeAdapter([
            _result(_make_step(fallback), status=StepStatus.COMPLETED, output_text="fallback output"),
        ])

        with (
            patch("gracekelly.core.router.list_models", return_value=(primary, fallback)),
            patch(
                "gracekelly.core.router._default_settings",
                replace(_default_settings, enable_model_fallback=True),
            ),
        ):
            router = ExecutionRouter(
                dry_run_adapter=_FakeAdapter([]),
                api_adapters={"anthropic": api_adapter},
                browser_adapter=browser_adapter,
            )
            batch = router.execute(
                task_id="t1",
                prompt="Q",
                plan=_make_plan(step),
                reasoning=False,
                metadata={},
            )

        self.assertEqual(batch.task_status, TaskStatus.COMPLETED)
        self.assertEqual(batch.results[0].model_id, "claude-sonnet-4-6-api")
        self.assertEqual(batch.results[0].output_text, "fallback output")
        self.assertTrue(batch.results[0].details["fallback_used"])
        self.assertEqual(batch.results[0].details["fallback_from_model"], "claude-sonnet-4-6")
        self.assertEqual(batch.results[0].details["fallback_reason"], "auth_failed")
        self.assertEqual(batch.results[0].details["primary_failure_message"], "login required")
        self.assertEqual(browser_adapter.calls, ["claude-sonnet-4-6"])
        self.assertEqual(api_adapter.calls, ["claude-sonnet-4-6-api"])

    def test_fallback_triggers_on_provider_unavailable_when_enabled(self) -> None:
        primary = _make_spec(
            "claude-sonnet-4-6",
            adapter_kind="browser",
            provider="perplexity",
            provider_model_id="Claude Sonnet 4.6",
            fallback_model_id="claude-sonnet-4-6-api",
        )
        fallback = _make_spec(
            "claude-sonnet-4-6-api",
            adapter_kind="api",
            provider="anthropic",
            provider_model_id="claude-sonnet-4-6-20250514",
        )
        step = _make_step(primary)
        browser_adapter = _FakeAdapter([
            _result(
                step,
                status=StepStatus.FAILED,
                failure_code=FailureCode.PROVIDER_UNAVAILABLE,
                failure_message="browser unavailable",
            ),
        ])
        api_adapter = _FakeAdapter([
            _result(_make_step(fallback), status=StepStatus.COMPLETED, output_text="fallback output"),
        ])

        with patch("gracekelly.core.router.list_models", return_value=(primary, fallback)):
            router = ExecutionRouter(
                dry_run_adapter=_FakeAdapter([]),
                api_adapters={"anthropic": api_adapter},
                browser_adapter=browser_adapter,
                settings=Settings(enable_model_fallback=True),
            )
            batch = router.execute(
                task_id="t1",
                prompt="Q",
                plan=_make_plan(step),
                reasoning=False,
                metadata={},
            )

        self.assertEqual(batch.task_status, TaskStatus.COMPLETED)
        self.assertEqual(batch.results[0].details["fallback_reason"], "provider_unavailable")
        self.assertEqual(api_adapter.calls, ["claude-sonnet-4-6-api"])

    def test_fallback_triggers_on_timeout_when_enabled(self) -> None:
        primary = _make_spec(
            "claude-sonnet-4-6",
            adapter_kind="browser",
            provider="perplexity",
            provider_model_id="Claude Sonnet 4.6",
            fallback_model_id="claude-sonnet-4-6-api",
        )
        fallback = _make_spec(
            "claude-sonnet-4-6-api",
            adapter_kind="api",
            provider="anthropic",
            provider_model_id="claude-sonnet-4-6-20250514",
        )
        step = _make_step(primary)
        browser_adapter = _FakeAdapter([
            _result(
                step,
                status=StepStatus.FAILED,
                failure_code=FailureCode.TIMEOUT,
                failure_message="timed out",
            ),
        ])
        api_adapter = _FakeAdapter([
            _result(_make_step(fallback), status=StepStatus.COMPLETED, output_text="fallback output"),
        ])

        with (
            patch("gracekelly.core.router.list_models", return_value=(primary, fallback)),
            patch(
                "gracekelly.core.router._default_settings",
                replace(_default_settings, enable_model_fallback=True),
            ),
        ):
            router = ExecutionRouter(
                dry_run_adapter=_FakeAdapter([]),
                api_adapters={"anthropic": api_adapter},
                browser_adapter=browser_adapter,
            )
            batch = router.execute(
                task_id="t1",
                prompt="Q",
                plan=_make_plan(step),
                reasoning=False,
                metadata={},
            )

        self.assertEqual(batch.task_status, TaskStatus.COMPLETED)
        self.assertEqual(batch.results[0].details["fallback_reason"], "timeout")
        self.assertEqual(api_adapter.calls, ["claude-sonnet-4-6-api"])

    def test_fallback_does_not_trigger_on_rate_limited(self) -> None:
        primary = _make_spec(
            "claude-sonnet-4-6",
            adapter_kind="browser",
            provider="perplexity",
            provider_model_id="Claude Sonnet 4.6",
            fallback_model_id="claude-sonnet-4-6-api",
        )
        fallback = _make_spec(
            "claude-sonnet-4-6-api",
            adapter_kind="api",
            provider="anthropic",
            provider_model_id="claude-sonnet-4-6-20250514",
        )
        step = _make_step(primary)
        browser_adapter = _FakeAdapter([
            _result(
                step,
                status=StepStatus.FAILED,
                failure_code=FailureCode.RATE_LIMITED,
                failure_message="limited",
            ),
        ])
        api_adapter = _FakeAdapter([
            _result(_make_step(fallback), status=StepStatus.COMPLETED, output_text="fallback output"),
        ])

        with (
            patch("gracekelly.core.router.list_models", return_value=(primary, fallback)),
            patch(
                "gracekelly.core.router._default_settings",
                replace(_default_settings, enable_model_fallback=True),
            ),
        ):
            router = ExecutionRouter(
                dry_run_adapter=_FakeAdapter([]),
                api_adapters={"anthropic": api_adapter},
                browser_adapter=browser_adapter,
            )
            batch = router.execute(
                task_id="t1",
                prompt="Q",
                plan=_make_plan(step),
                reasoning=False,
                metadata={},
            )

        self.assertEqual(batch.task_status, TaskStatus.FAILED)
        self.assertEqual(batch.failure_code, FailureCode.RATE_LIMITED)
        self.assertNotIn("fallback_used", batch.results[0].details)
        self.assertEqual(api_adapter.calls, [])

    def test_fallback_does_not_trigger_on_model_mismatch(self) -> None:
        primary = _make_spec(
            "claude-sonnet-4-6",
            adapter_kind="browser",
            provider="perplexity",
            provider_model_id="Claude Sonnet 4.6",
            fallback_model_id="claude-sonnet-4-6-api",
        )
        fallback = _make_spec(
            "claude-sonnet-4-6-api",
            adapter_kind="api",
            provider="anthropic",
            provider_model_id="claude-sonnet-4-6-20250514",
        )
        step = _make_step(primary)
        browser_adapter = _FakeAdapter([
            _result(
                step,
                status=StepStatus.FAILED,
                failure_code=FailureCode.MODEL_MISMATCH,
                failure_message="wrong model",
            ),
        ])
        api_adapter = _FakeAdapter([
            _result(_make_step(fallback), status=StepStatus.COMPLETED, output_text="fallback output"),
        ])

        with (
            patch("gracekelly.core.router.list_models", return_value=(primary, fallback)),
            patch(
                "gracekelly.core.router._default_settings",
                replace(_default_settings, enable_model_fallback=True),
            ),
        ):
            router = ExecutionRouter(
                dry_run_adapter=_FakeAdapter([]),
                api_adapters={"anthropic": api_adapter},
                browser_adapter=browser_adapter,
            )
            batch = router.execute(
                task_id="t1",
                prompt="Q",
                plan=_make_plan(step),
                reasoning=False,
                metadata={},
            )

        self.assertEqual(batch.task_status, TaskStatus.FAILED)
        self.assertEqual(batch.failure_code, FailureCode.MODEL_MISMATCH)
        self.assertNotIn("fallback_used", batch.results[0].details)
        self.assertEqual(api_adapter.calls, [])

    def test_fallback_does_not_trigger_without_fallback_model_id(self) -> None:
        primary = _make_spec(
            "sonar",
            adapter_kind="browser",
            provider="perplexity",
            provider_model_id="Sonar",
        )
        step = _make_step(primary)
        browser_adapter = _FakeAdapter([
            _result(
                step,
                status=StepStatus.FAILED,
                failure_code=FailureCode.AUTH_FAILED,
                failure_message="login required",
            ),
        ])
        api_adapter = _FakeAdapter([])

        with (
            patch("gracekelly.core.router.list_models", return_value=(primary,)),
            patch(
                "gracekelly.core.router._default_settings",
                replace(_default_settings, enable_model_fallback=True),
            ),
        ):
            router = ExecutionRouter(
                dry_run_adapter=_FakeAdapter([]),
                api_adapters={"anthropic": api_adapter},
                browser_adapter=browser_adapter,
            )
            batch = router.execute(
                task_id="t1",
                prompt="Q",
                plan=_make_plan(step),
                reasoning=False,
                metadata={},
            )

        self.assertEqual(batch.task_status, TaskStatus.FAILED)
        self.assertEqual(batch.failure_code, FailureCode.AUTH_FAILED)
        self.assertNotIn("fallback_used", batch.results[0].details)
        self.assertEqual(api_adapter.calls, [])

    def test_fallback_no_second_level_on_fallback_failure(self) -> None:
        primary = _make_spec(
            "claude-sonnet-4-6",
            adapter_kind="browser",
            provider="perplexity",
            provider_model_id="Claude Sonnet 4.6",
            fallback_model_id="claude-sonnet-4-6-api",
        )
        fallback = _make_spec(
            "claude-sonnet-4-6-api",
            adapter_kind="api",
            provider="anthropic",
            provider_model_id="claude-sonnet-4-6-20250514",
        )
        step = _make_step(primary)
        browser_adapter = _FakeAdapter([
            _result(
                step,
                status=StepStatus.FAILED,
                failure_code=FailureCode.AUTH_FAILED,
                failure_message="login required",
            ),
        ])
        api_adapter = _FakeAdapter([
            _result(
                _make_step(fallback),
                status=StepStatus.FAILED,
                failure_code=FailureCode.PROVIDER_UNAVAILABLE,
                failure_message="api unavailable",
            ),
        ])

        with (
            patch("gracekelly.core.router.list_models", return_value=(primary, fallback)),
            patch(
                "gracekelly.core.router._default_settings",
                replace(_default_settings, enable_model_fallback=True),
            ),
        ):
            router = ExecutionRouter(
                dry_run_adapter=_FakeAdapter([]),
                api_adapters={"anthropic": api_adapter},
                browser_adapter=browser_adapter,
            )
            batch = router.execute(
                task_id="t1",
                prompt="Q",
                plan=_make_plan(step),
                reasoning=False,
                metadata={},
            )

        self.assertEqual(batch.task_status, TaskStatus.FAILED)
        self.assertEqual(batch.failure_code, FailureCode.PROVIDER_UNAVAILABLE)
        self.assertEqual(batch.results[0].model_id, "claude-sonnet-4-6-api")
        self.assertTrue(batch.results[0].details["fallback_used"])
        self.assertEqual(batch.results[0].details["fallback_reason"], "auth_failed")
        self.assertEqual(browser_adapter.calls, ["claude-sonnet-4-6"])
        self.assertEqual(api_adapter.calls, ["claude-sonnet-4-6-api"])

    def test_model_spec_fallback_field_serializes(self) -> None:
        spec = ModelSpec(
            id="x",
            display_name="X",
            aliases=("x",),
            adapter_kind="api",
            provider="openai",
            provider_model_id="x",
            timeout_seconds=30,
            expected_latency_class="fast",
            concurrency_limit=4,
            reasoning_capable=True,
            fallback_model_id="y",
        )
        legacy_payload = {
            "id": "legacy",
            "display_name": "Legacy",
            "aliases": ["legacy"],
            "adapter_kind": "api",
            "provider": "openai",
            "provider_model_id": "legacy",
            "timeout_seconds": 30,
            "expected_latency_class": "fast",
            "concurrency_limit": 4,
            "reasoning_capable": False,
        }

        self.assertEqual(asdict(spec)["fallback_model_id"], "y")
        self.assertEqual(build_browser_model_spec("Claude Sonnet 4.6").fallback_model_id, "claude-sonnet-4-6-api")
        self.assertEqual(build_browser_model_spec("GPT-5.4").fallback_model_id, "gpt-5-4-api")
        self.assertIsNone(build_browser_model_spec("Sonar").fallback_model_id)
        self.assertIsNone(deserialize_model_spec(legacy_payload).fallback_model_id)


def test_try_fallback_logs_attempt_and_success(caplog: pytest.LogCaptureFixture) -> None:
    primary = _make_spec(
        "claude-sonnet-4-6",
        adapter_kind="browser",
        provider="perplexity",
        provider_model_id="Claude Sonnet 4.6",
        fallback_model_id="claude-sonnet-4-6-api",
    )
    fallback = _make_spec(
        "claude-sonnet-4-6-api",
        adapter_kind="api",
        provider="anthropic",
        provider_model_id="claude-sonnet-4-6-20250514",
    )
    step = _make_step(primary)
    browser_adapter = _FakeAdapter([
        _result(
            step,
            status=StepStatus.FAILED,
            failure_code=FailureCode.AUTH_FAILED,
            failure_message="login required",
        ),
    ])
    api_adapter = _FakeAdapter([
        _result(_make_step(fallback), status=StepStatus.COMPLETED, output_text="fallback output"),
    ])
    caplog.handler.setLevel(logging.INFO)

    with patch("gracekelly.core.router.list_models", return_value=(primary, fallback)):
        router = ExecutionRouter(
            dry_run_adapter=_FakeAdapter([]),
            api_adapters={"anthropic": api_adapter},
            browser_adapter=browser_adapter,
            settings=Settings(enable_model_fallback=True),
        )
        with caplog.at_level(logging.INFO, logger="gracekelly.core.router"):
            batch = router.execute(
                task_id="t1",
                prompt="Q",
                plan=_make_plan(step),
                reasoning=False,
                metadata={},
            )

    attempt_records = [
        record
        for record in caplog.records
        if record.name == "gracekelly.core.router" and "fallback attempting:" in record.getMessage()
    ]
    assert len(attempt_records) == 1
    assert attempt_records[0].getMessage() == "fallback attempting: claude-sonnet-4-6 -> claude-sonnet-4-6-api reason=auth_failed"
    assert getattr(attempt_records[0], "task_id") == "t1"
    assert getattr(attempt_records[0], "primary_failure_code") == "auth_failed"
    assert getattr(attempt_records[0], "fallback_to") == "claude-sonnet-4-6-api"

    success_records = [
        record
        for record in caplog.records
        if record.name == "gracekelly.core.router" and "fallback succeeded:" in record.getMessage()
    ]
    assert len(success_records) == 1
    assert success_records[0].getMessage() == "fallback succeeded: claude-sonnet-4-6 -> claude-sonnet-4-6-api"
    assert getattr(success_records[0], "task_id") == "t1"
    assert getattr(success_records[0], "primary_failure_code") == "auth_failed"
    assert getattr(success_records[0], "fallback_to") == "claude-sonnet-4-6-api"
    assert batch.results[0].model_id == "claude-sonnet-4-6-api"


def test_try_fallback_logs_skip_reason_when_disabled(caplog: pytest.LogCaptureFixture) -> None:
    primary = _make_spec(
        "claude-sonnet-4-6",
        adapter_kind="browser",
        provider="perplexity",
        provider_model_id="Claude Sonnet 4.6",
        fallback_model_id="claude-sonnet-4-6-api",
    )
    fallback = _make_spec(
        "claude-sonnet-4-6-api",
        adapter_kind="api",
        provider="anthropic",
        provider_model_id="claude-sonnet-4-6-20250514",
    )
    step = _make_step(primary)
    browser_adapter = _FakeAdapter([
        _result(
            step,
            status=StepStatus.FAILED,
            failure_code=FailureCode.PROVIDER_UNAVAILABLE,
            failure_message="browser unavailable",
        ),
    ])
    caplog.handler.setLevel(logging.DEBUG)

    with patch("gracekelly.core.router.list_models", return_value=(primary, fallback)):
        router = ExecutionRouter(
            dry_run_adapter=_FakeAdapter([]),
            api_adapters={},
            browser_adapter=browser_adapter,
            settings=Settings(enable_model_fallback=False),
        )
        with caplog.at_level(logging.DEBUG, logger="gracekelly.core.router"):
            batch = router.execute(
                task_id="t1",
                prompt="Q",
                plan=_make_plan(step),
                reasoning=False,
                metadata={},
            )

    skip_records = [
        record
        for record in caplog.records
        if record.name == "gracekelly.core.router" and "fallback skipped:" in record.getMessage()
    ]
    assert len(skip_records) == 1
    assert skip_records[0].getMessage() == "fallback skipped: disabled"
    assert getattr(skip_records[0], "task_id") == "t1"
    assert getattr(skip_records[0], "step_index") == 0
    assert getattr(skip_records[0], "model_id") == "claude-sonnet-4-6"
    assert getattr(skip_records[0], "skip_reason") == "disabled"
    assert batch.failure_code == FailureCode.PROVIDER_UNAVAILABLE


if __name__ == "__main__":
    unittest.main()
