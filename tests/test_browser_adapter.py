from __future__ import annotations

import asyncio
import unittest
from collections.abc import Callable

import pytest

from gracekelly.adapters.browser.automation import (
    BrowserAuthStatus,
    BrowserAutomationPort,
    BrowserExecutionOutput,
    BrowserModelSelection,
    BrowserProfileBusyError,
)
from gracekelly.adapters.browser.perplexity import PerplexityBrowserAdapter
from gracekelly.adapters.browser.policy import AuthRecoveryPolicy, ModelVerificationPolicy, PopupPolicy, SubmitPolicy
from gracekelly.adapters.browser.session import BrowserSessionConfig, BrowserSessionManager
from gracekelly.core.contracts import (
    CancellationToken,
    ExecutionRequest,
    FailureCode,
    FileAttachment,
    StepStatus,
)

pytestmark = pytest.mark.usefixtures("inject_shared_test_factories")


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

    def dismiss_popups(self, policy: PopupPolicy) -> None:
        return None

    def auth_status(self, policy: AuthRecoveryPolicy) -> BrowserAuthStatus:
        if self._logged_in:
            return BrowserAuthStatus(logged_in=True)
        return BrowserAuthStatus(logged_in=False, reason="Login required.")

    def recover_auth(self, policy: AuthRecoveryPolicy) -> BrowserAuthStatus:
        return self.auth_status(policy)

    def select_model(self, *, provider_model_id: str, policy: ModelVerificationPolicy) -> BrowserModelSelection:
        actual = self._actual_label or provider_model_id
        return BrowserModelSelection(
            requested_label=provider_model_id,
            actual_label=actual,
        )

    def submit_prompt(self, *, prompt: str, policy: SubmitPolicy, timeout_seconds: int) -> BrowserExecutionOutput:
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
    build_request: Callable[..., ExecutionRequest]
    build_session_manager: Callable[..., BrowserSessionManager]

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

    def test_browser_adapter_attaches_files_before_prompt_submission(self) -> None:
        attachment = FileAttachment(name="photo.png", content_type="image/png", data=b"png-bytes")
        events: list[str] = []

        class AttachmentAwareAutomation(FakeBrowserAutomation):
            def __init__(self) -> None:
                super().__init__()
                self.captured_attachments: tuple[FileAttachment, ...] = ()

            def attach_files(self, attachments: tuple[FileAttachment, ...]) -> None:
                events.append("attach")
                self.captured_attachments = attachments

            def submit_prompt(
                self,
                *,
                prompt: str,
                policy: SubmitPolicy,
                timeout_seconds: int,
            ) -> BrowserExecutionOutput:
                events.append("submit")
                return super().submit_prompt(prompt=prompt, policy=policy, timeout_seconds=timeout_seconds)

        automation = AttachmentAwareAutomation()
        adapter = PerplexityBrowserAdapter(
            session_manager=self.build_session_manager(),
            automation=automation,
        )

        result = adapter.execute(self.build_request(attachments=(attachment,)))

        self.assertEqual(result.status, StepStatus.COMPLETED)
        self.assertEqual(automation.captured_attachments, (attachment,))
        self.assertEqual(events, ["attach", "submit"])

    def test_browser_adapter_skips_file_attachment_when_request_has_no_files(self) -> None:
        class AttachmentAwareAutomation(FakeBrowserAutomation):
            def __init__(self) -> None:
                super().__init__()
                self.attach_calls = 0

            def attach_files(self, attachments: tuple[FileAttachment, ...]) -> None:
                self.attach_calls += 1

        automation = AttachmentAwareAutomation()
        adapter = PerplexityBrowserAdapter(
            session_manager=self.build_session_manager(),
            automation=automation,
        )

        result = adapter.execute(self.build_request())

        self.assertEqual(result.status, StepStatus.COMPLETED)
        self.assertEqual(automation.attach_calls, 0)

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
            def submit_prompt(self, *, prompt: str, policy: SubmitPolicy, timeout_seconds: int) -> BrowserExecutionOutput:
                raise RuntimeError("unexpected browser crash")

        adapter = PerplexityBrowserAdapter(
            session_manager=self.build_session_manager(),
            automation=CrashingBrowserAutomation(),
        )

        result = adapter.execute(self.build_request())

        self.assertEqual(result.status, StepStatus.FAILED)
        self.assertEqual(result.failure_code, FailureCode.UNKNOWN_ERROR)
        assert result.failure_message is not None
        self.assertIn("unexpected browser crash", result.failure_message)

    def test_browser_adapter_maps_permission_error_to_auth_failed(self) -> None:
        class PromptBlockedBrowserAutomation(FakeBrowserAutomation):
            def submit_prompt(self, *, prompt: str, policy: SubmitPolicy, timeout_seconds: int) -> BrowserExecutionOutput:
                raise PermissionError("Perplexity sign-in overlay blocked prompt submission.")

        adapter = PerplexityBrowserAdapter(
            session_manager=self.build_session_manager(),
            automation=PromptBlockedBrowserAutomation(),
        )

        result = adapter.execute(self.build_request())

        self.assertEqual(result.status, StepStatus.FAILED)
        self.assertEqual(result.failure_code, FailureCode.AUTH_FAILED)
        assert result.failure_message is not None
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
        assert result.failure_message is not None
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


class ModelMatchesExpectedTests(unittest.TestCase):
    _make_adapter: Callable[..., PerplexityBrowserAdapter]

    def test_exact_match_returns_true(self) -> None:
        adapter = self._make_adapter()
        self.assertTrue(adapter._model_matches_expected("sonar", "sonar"))

    def test_different_labels_without_alias_match_returns_false(self) -> None:
        adapter = self._make_adapter(allow_alias_match=False)
        self.assertFalse(adapter._model_matches_expected("sonar-pro", "sonar"))

    def test_alias_match_enabled_equivalent_models_returns_true(self) -> None:
        adapter = self._make_adapter(allow_alias_match=True)
        # "Claude Sonnet 4.6" and "Claude 4.6" are aliases of the same model id →
        # exact match fails, but models_equivalent returns True → method returns True
        self.assertTrue(adapter._model_matches_expected("Claude Sonnet 4.6", "Claude 4.6"))

    def test_alias_match_disabled_even_when_models_are_equivalent(self) -> None:
        adapter = self._make_adapter(allow_alias_match=False)
        # Even if labels would be equivalent, alias match is disabled → False
        self.assertFalse(adapter._model_matches_expected("sonar", "sonar-pro"))


class EnsureAuthTests(unittest.TestCase):
    """Direct tests for _ensure_auth branches."""

    _session_manager: Callable[[], BrowserSessionManager]

    def test_ensure_auth_returns_status_when_already_logged_in(self) -> None:
        """_ensure_auth should return immediately when auth_status reports logged_in=True."""
        class LoggedInAutomation(FakeBrowserAutomation):
            def auth_status(self, policy: AuthRecoveryPolicy) -> BrowserAuthStatus:
                return BrowserAuthStatus(logged_in=True)

        adapter = PerplexityBrowserAdapter(
            session_manager=self._session_manager(),
            automation=LoggedInAutomation(),
        )
        status = adapter._ensure_auth()
        self.assertTrue(status.logged_in)

    def test_ensure_auth_calls_recover_when_not_logged_in_and_relogin_allowed(self) -> None:
        """When not logged in and allow_relogin=True, recover_auth should be called."""
        recovered: list[bool] = []

        class RecoverableAutomation(FakeBrowserAutomation):
            def auth_status(self, policy: AuthRecoveryPolicy) -> BrowserAuthStatus:
                return BrowserAuthStatus(logged_in=False)

            def recover_auth(self, policy: AuthRecoveryPolicy) -> BrowserAuthStatus:
                recovered.append(True)
                return BrowserAuthStatus(logged_in=True)

        adapter = PerplexityBrowserAdapter(
            session_manager=self._session_manager(),
            automation=RecoverableAutomation(),
            auth_recovery_policy=AuthRecoveryPolicy(allow_relogin=True),
        )
        status = adapter._ensure_auth()
        self.assertTrue(recovered, "recover_auth was not called")
        self.assertTrue(status.logged_in)

    def test_ensure_auth_returns_failed_status_when_relogin_not_allowed(self) -> None:
        """When not logged in and allow_relogin=False, auth status returned without recovery."""
        adapter = PerplexityBrowserAdapter(
            session_manager=self._session_manager(),
            automation=FakeBrowserAutomation(logged_in=False),
            auth_recovery_policy=AuthRecoveryPolicy(allow_relogin=False),
        )
        status = adapter._ensure_auth()
        self.assertFalse(status.logged_in)


class CancelledResultTests(unittest.TestCase):
    """Direct tests for _cancelled helper."""

    def test_cancelled_returns_cancelled_status(self) -> None:
        session_manager = BrowserSessionManager(
            BrowserSessionConfig(
                enabled=True,
                provider="perplexity",
                base_url="https://www.perplexity.ai",
                profile_dir="D:\\Profiles\\GraceKelly",
            )
        )
        adapter = PerplexityBrowserAdapter(session_manager=session_manager)
        result = adapter._cancelled("kimi-k2-5", "Kimi K2.5")
        self.assertEqual(result.status, StepStatus.CANCELLED)
        self.assertEqual(result.model_id, "kimi-k2-5")
        self.assertEqual(result.model_display_name, "Kimi K2.5")
        self.assertTrue(result.details["cancelled"])
        self.assertEqual(result.execution_mode, "browser")


if __name__ == "__main__":
    unittest.main()
