from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

from gracekelly.adapters.browser.policy import AuthRecoveryPolicy, ModelVerificationPolicy, PopupPolicy, SubmitPolicy
from gracekelly.adapters.browser.session import BrowserSessionManager

if TYPE_CHECKING:
    from gracekelly.core.contracts import FileAttachment


@dataclass(frozen=True, slots=True)
class BrowserAuthStatus:
    logged_in: bool
    reason: str | None = None


@dataclass(frozen=True, slots=True)
class BrowserModelSelection:
    requested_label: str
    actual_label: str
    details: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class BrowserExecutionOutput:
    output_text: str
    details: dict[str, Any] = field(default_factory=dict)


class BrowserProfileBusyError(RuntimeError):
    pass


class BrowserAutomationPort(ABC):
    @abstractmethod
    def ensure_session(self, session_manager: BrowserSessionManager) -> None:
        raise NotImplementedError

    @abstractmethod
    def dismiss_popups(self, policy: PopupPolicy) -> None:
        raise NotImplementedError

    @abstractmethod
    def auth_status(self, policy: AuthRecoveryPolicy) -> BrowserAuthStatus:
        raise NotImplementedError

    @abstractmethod
    def recover_auth(self, policy: AuthRecoveryPolicy) -> BrowserAuthStatus:
        raise NotImplementedError

    @abstractmethod
    def select_model(
        self,
        *,
        provider_model_id: str,
        policy: ModelVerificationPolicy,
    ) -> BrowserModelSelection:
        raise NotImplementedError

    @abstractmethod
    def submit_prompt(
        self,
        *,
        prompt: str,
        policy: SubmitPolicy,
        timeout_seconds: int,
    ) -> BrowserExecutionOutput:
        raise NotImplementedError

    def attach_files(self, attachments: tuple[FileAttachment, ...]) -> None:
        return None

    def reset_page_state(self) -> bool:
        """Return page to a clean state before a new execution. Default: no-op."""
        return False

    def healthcheck(self) -> dict[str, Any]:
        return {
            "status": "degraded",
            "implemented": False,
        }


class NullBrowserAutomation(BrowserAutomationPort):
    def ensure_session(self, session_manager: BrowserSessionManager) -> None:
        raise NotImplementedError("Browser automation driver is not configured.")

    def dismiss_popups(self, policy: PopupPolicy) -> None:
        raise NotImplementedError("Browser automation driver is not configured.")

    def auth_status(self, policy: AuthRecoveryPolicy) -> BrowserAuthStatus:
        raise NotImplementedError("Browser automation driver is not configured.")

    def recover_auth(self, policy: AuthRecoveryPolicy) -> BrowserAuthStatus:
        raise NotImplementedError("Browser automation driver is not configured.")

    def select_model(
        self,
        *,
        provider_model_id: str,
        policy: ModelVerificationPolicy,
    ) -> BrowserModelSelection:
        raise NotImplementedError("Browser automation driver is not configured.")

    def submit_prompt(
        self,
        *,
        prompt: str,
        policy: SubmitPolicy,
        timeout_seconds: int,
    ) -> BrowserExecutionOutput:
        raise NotImplementedError("Browser automation driver is not configured.")

    def healthcheck(self) -> dict[str, Any]:
        return {
            "status": "degraded",
            "implemented": False,
            "reason": "No browser automation driver configured.",
        }
