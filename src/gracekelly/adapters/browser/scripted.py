from __future__ import annotations

from dataclasses import dataclass

from gracekelly.adapters.browser.automation import (
    BrowserAuthStatus,
    BrowserAutomationPort,
    BrowserExecutionOutput,
    BrowserModelSelection,
)
from gracekelly.adapters.browser.policy import (
    AuthRecoveryPolicy,
    ModelVerificationPolicy,
    PopupPolicy,
    SubmitPolicy,
)
from gracekelly.adapters.browser.session import BrowserSessionManager


@dataclass(frozen=True, slots=True)
class ScriptedBrowserScenario:
    logged_in: bool = True
    actual_model_label: str | None = None
    output_text: str = "scripted browser result"


class ScriptedBrowserAutomation(BrowserAutomationPort):
    def __init__(self, scenario: ScriptedBrowserScenario | None = None) -> None:
        self._scenario = scenario or ScriptedBrowserScenario()

    def ensure_session(self, session_manager: BrowserSessionManager) -> None:
        if not session_manager.state.configured:
            raise NotImplementedError("Browser session is not configured yet.")

    def dismiss_popups(self, policy: PopupPolicy) -> None:
        return None

    def auth_status(self, policy: AuthRecoveryPolicy) -> BrowserAuthStatus:
        if self._scenario.logged_in:
            return BrowserAuthStatus(logged_in=True)
        return BrowserAuthStatus(
            logged_in=False,
            reason="Scripted browser session is logged out.",
        )

    def recover_auth(self, policy: AuthRecoveryPolicy) -> BrowserAuthStatus:
        return self.auth_status(policy)

    def select_model(
        self,
        *,
        provider_model_id: str,
        policy: ModelVerificationPolicy,
    ) -> BrowserModelSelection:
        return BrowserModelSelection(
            requested_label=provider_model_id,
            actual_label=self._scenario.actual_model_label or provider_model_id,
            details={"driver": "scripted"},
        )

    def submit_prompt(
        self,
        *,
        prompt: str,
        policy: SubmitPolicy,
        timeout_seconds: int,
    ) -> BrowserExecutionOutput:
        return BrowserExecutionOutput(
            output_text=self._scenario.output_text,
            details={
                "driver": "scripted",
                "submitted_prompt": prompt,
                "timeout_seconds": timeout_seconds,
            },
        )

    def healthcheck(self) -> dict[str, object]:
        return {
            "status": "ok",
            "implemented": True,
            "driver": "scripted",
            "logged_in": self._scenario.logged_in,
        }
