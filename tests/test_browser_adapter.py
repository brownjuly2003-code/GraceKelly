from __future__ import annotations

import asyncio
import unittest

from gracekelly.adapters.browser.automation import (
    BrowserAuthStatus,
    BrowserAutomationPort,
    BrowserExecutionOutput,
    BrowserModelSelection,
    BrowserProfileBusyError,
)
from gracekelly.adapters.browser.perplexity import PerplexityBrowserAdapter
from gracekelly.adapters.browser.policy import AuthRecoveryPolicy
from gracekelly.adapters.browser.session import BrowserSessionConfig, BrowserSessionManager
from gracekelly.core.contracts import (
    CancellationToken,
    ExecutionBackend,
    ExecutionPlan,
    ExecutionRequest,
    ExecutionStep,
    FailureCode,
    StepStatus,
)
from gracekelly.core.models import resolve_model


class FakeBrowserAutomation(BrowserAutomationPort):
    def __init__(
        self,
        *,
        logged_in: bool = True,
        actual_label: str | None = None,
        output_text: str = "browser result",
    ) -> None:
        self._logged_in = logged_in
        self._actual_label = actual_label
        self._output_text = output_text

    def ensure_session(self, session_manager: BrowserSessionManager) -> None:
        return None

    def dismiss_popups(self, policy) -> None:
        return None

    def auth_status(self, policy) -> BrowserAuthStatus:
        if self._logged_in:
            return BrowserAuthStatus(logged_in=True)
        return BrowserAuthStatus(logged_in=False, reason="Login required.")

    def recover_auth(self, policy) -> BrowserAuthStatus:
        return self.auth_status(policy)

    def select_model(self, *, provider_model_id: str, policy) -> BrowserModelSelection:
        actual = self._actual_label or provider_model_id
        return BrowserModelSelection(
            requested_label=provider_model_id,
            actual_label=actual,
        )

    def submit_prompt(self, *, prompt: str, policy, timeout_seconds: int) -> BrowserExecutionOutput:
        return BrowserExecutionOutput(
            output_text=self._output_text,
            details={"submitted_prompt": prompt, "timeout_seconds": timeout_seconds},
        )

    def healthcheck(self) -> dict[str, object]:
        return {
            "status": "ok",
            "implemented": True,
        }


class BrowserAdapterTests(unittest.TestCase):
    def build_request(self, *, cancellation: CancellationToken | None = None) -> ExecutionRequest:
        model = resolve_model("Kimi K2")
        step = ExecutionStep(
            model=model,
            backend=ExecutionBackend.BROWSER,
            provider=model.provider,
            provider_model_id=model.provider_model_id,
            step_index=1,
        )
        plan = ExecutionPlan(
            steps=(step,),
            quorum=1,
            merge_strategy="first_success",
            dry_run=False,
            adapter_hint="auto",
            cancel_on_quorum=True,
        )
        return ExecutionRequest(
            task_id="task-browser-1",
            prompt="hello",
            plan=plan,
            step=step,
            reasoning=False,
            metadata={},
            cancellation=cancellation,
        )

    def build_session_manager(self, *, enabled: bool = True, profile_dir: str | None = "D:\\Profiles\\GraceKelly") -> BrowserSessionManager:
        return BrowserSessionManager(
            BrowserSessionConfig(
                enabled=enabled,
                provider="perplexity",
                base_url="https://www.perplexity.ai",
                profile_dir=profile_dir,
            )
        )

    def test_browser_adapter_returns_provider_unavailable_when_not_configured(self) -> None:
        adapter = PerplexityBrowserAdapter(session_manager=self.build_session_manager(enabled=False, profile_dir=None))

        result = adapter.execute(self.build_request())

        self.assertEqual(result.failure_code, FailureCode.PROVIDER_UNAVAILABLE)
        self.assertEqual(result.execution_mode, "browser")
        self.assertEqual(result.adapter_name, "browser.perplexity")
        self.assertEqual(result.status, StepStatus.FAILED)

    def test_browser_adapter_can_complete_with_automation_port(self) -> None:
        adapter = PerplexityBrowserAdapter(
            session_manager=self.build_session_manager(),
            automation=FakeBrowserAutomation(output_text="browser success"),
        )

        result = adapter.execute(self.build_request())

        self.assertEqual(result.status, StepStatus.COMPLETED)
        self.assertEqual(result.output_text, "browser success")
        self.assertEqual(result.details["actual_model_label"], "Kimi K2.5")

    def test_browser_adapter_returns_auth_failed_when_login_missing(self) -> None:
        adapter = PerplexityBrowserAdapter(
            session_manager=self.build_session_manager(),
            automation=FakeBrowserAutomation(logged_in=False),
            auth_recovery_policy=AuthRecoveryPolicy(allow_relogin=False),
        )

        result = adapter.execute(self.build_request())

        self.assertEqual(result.status, StepStatus.FAILED)
        self.assertEqual(result.failure_code, FailureCode.AUTH_FAILED)

    def test_browser_adapter_returns_model_mismatch_when_ui_model_differs(self) -> None:
        adapter = PerplexityBrowserAdapter(
            session_manager=self.build_session_manager(),
            automation=FakeBrowserAutomation(actual_label="Claude Sonnet 4.6"),
        )

        result = adapter.execute(self.build_request())

        self.assertEqual(result.status, StepStatus.FAILED)
        self.assertEqual(result.failure_code, FailureCode.MODEL_MISMATCH)

    def test_browser_adapter_honors_cancellation_before_execution(self) -> None:
        token = CancellationToken()
        token.request_cancel()
        adapter = PerplexityBrowserAdapter(
            session_manager=self.build_session_manager(),
            automation=FakeBrowserAutomation(),
        )

        result = adapter.execute(self.build_request(cancellation=token))

        self.assertEqual(result.status, StepStatus.CANCELLED)

    def test_browser_adapter_maps_unexpected_runtime_error_to_unknown_error(self) -> None:
        class CrashingBrowserAutomation(FakeBrowserAutomation):
            def submit_prompt(self, *, prompt: str, policy, timeout_seconds: int) -> BrowserExecutionOutput:
                raise RuntimeError("unexpected browser crash")

        adapter = PerplexityBrowserAdapter(
            session_manager=self.build_session_manager(),
            automation=CrashingBrowserAutomation(),
        )

        result = adapter.execute(self.build_request())

        self.assertEqual(result.status, StepStatus.FAILED)
        self.assertEqual(result.failure_code, FailureCode.UNKNOWN_ERROR)
        self.assertIn("unexpected browser crash", result.failure_message)

    def test_browser_adapter_maps_permission_error_to_auth_failed(self) -> None:
        class PromptBlockedBrowserAutomation(FakeBrowserAutomation):
            def submit_prompt(self, *, prompt: str, policy, timeout_seconds: int) -> BrowserExecutionOutput:
                raise PermissionError("Perplexity sign-in overlay blocked prompt submission.")

        adapter = PerplexityBrowserAdapter(
            session_manager=self.build_session_manager(),
            automation=PromptBlockedBrowserAutomation(),
        )

        result = adapter.execute(self.build_request())

        self.assertEqual(result.status, StepStatus.FAILED)
        self.assertEqual(result.failure_code, FailureCode.AUTH_FAILED)
        self.assertIn("sign-in overlay", result.failure_message)

    def test_browser_adapter_maps_busy_profile_error_to_provider_unavailable(self) -> None:
        class BusyProfileBrowserAutomation(FakeBrowserAutomation):
            def ensure_session(self, session_manager: BrowserSessionManager) -> None:
                raise BrowserProfileBusyError("Browser profile directory is already in use.")

        adapter = PerplexityBrowserAdapter(
            session_manager=self.build_session_manager(),
            automation=BusyProfileBrowserAutomation(),
        )

        result = adapter.execute(self.build_request())

        self.assertEqual(result.status, StepStatus.FAILED)
        self.assertEqual(result.failure_code, FailureCode.PROVIDER_UNAVAILABLE)
        self.assertIn("already in use", result.failure_message)

    def test_browser_session_manager_state_returns_snapshot(self) -> None:
        session_manager = self.build_session_manager()
        session_manager.mark_active()

        snapshot = session_manager.state
        snapshot.active = False
        snapshot.last_error = "tampered"

        current = session_manager.state
        self.assertTrue(current.active)
        self.assertIsNone(current.last_error)

    def test_browser_session_manager_logs_state_changes(self) -> None:
        session_manager = self.build_session_manager()

        with self.assertLogs("gracekelly.adapters.browser.session", level="INFO") as captured:
            session_manager.mark_active()
            session_manager.mark_idle()
            session_manager.mark_error("browser offline")

        self.assertEqual(len(captured.output), 3)
        self.assertIn("marked active", captured.output[0])
        self.assertIn("marked idle", captured.output[1])
        self.assertIn("browser offline", captured.output[2])

    def test_browser_adapter_logs_successful_execution(self) -> None:
        adapter = PerplexityBrowserAdapter(
            session_manager=self.build_session_manager(),
            automation=FakeBrowserAutomation(output_text="browser success"),
        )

        with self.assertLogs("gracekelly.adapters.browser.perplexity", level="INFO") as captured:
            result = adapter.execute(self.build_request())

        self.assertEqual(result.status, StepStatus.COMPLETED)
        self.assertEqual(len(captured.output), 3)
        self.assertIn("Browser execution started", captured.output[0])
        self.assertIn("auth check", captured.output[1])
        self.assertIn("logged_in=True", captured.output[1])
        self.assertIn("Browser execution completed", captured.output[2])
        self.assertIn("duration_ms=", captured.output[2])

    def test_browser_adapter_logs_failed_execution(self) -> None:
        adapter = PerplexityBrowserAdapter(
            session_manager=self.build_session_manager(),
            automation=FakeBrowserAutomation(logged_in=False),
            auth_recovery_policy=AuthRecoveryPolicy(allow_relogin=False),
        )

        with self.assertLogs("gracekelly.adapters.browser.perplexity", level="WARNING") as captured:
            result = adapter.execute(self.build_request())

        self.assertEqual(result.status, StepStatus.FAILED)
        self.assertEqual(result.failure_code, FailureCode.AUTH_FAILED)
        self.assertEqual(len(captured.output), 1)
        self.assertIn("auth_failed", captured.output[0])

    def test_browser_adapter_close_marks_session_idle(self) -> None:
        class ClosableAutomation(FakeBrowserAutomation):
            def __init__(self) -> None:
                super().__init__()
                self.closed = False

            def close(self) -> None:
                self.closed = True

        session_manager = self.build_session_manager()
        session_manager.mark_active()
        automation = ClosableAutomation()
        adapter = PerplexityBrowserAdapter(
            session_manager=session_manager,
            automation=automation,
        )

        asyncio.run(adapter.close())

        self.assertTrue(automation.closed)
        self.assertFalse(session_manager.state.active)
        self.assertIsNone(session_manager.state.last_error)

    def test_browser_healthcheck_degrades_when_session_and_automation_runtime_disagree(self) -> None:
        class NotLaunchedAutomation(FakeBrowserAutomation):
            def healthcheck(self) -> dict[str, object]:
                return {
                    "status": "ok",
                    "implemented": True,
                    "driver": "playwright",
                    "launched": False,
                }

        session_manager = self.build_session_manager()
        session_manager.mark_active()
        adapter = PerplexityBrowserAdapter(
            session_manager=session_manager,
            automation=NotLaunchedAutomation(),
        )

        health = adapter.healthcheck()

        self.assertEqual(health["status"], "degraded")
        self.assertFalse(health["runtime_consistent"])


if __name__ == "__main__":
    unittest.main()
