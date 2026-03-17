from __future__ import annotations

from dataclasses import asdict

from gracekelly.adapters.browser.automation import (
    BrowserAutomationPort,
    BrowserAuthStatus,
    BrowserExecutionOutput,
    BrowserModelSelection,
    NullBrowserAutomation,
)
from gracekelly.adapters.browser.policy import (
    AuthRecoveryPolicy,
    ModelVerificationPolicy,
    PopupPolicy,
    SubmitPolicy,
)
from gracekelly.adapters.browser.session import BrowserSessionManager
from gracekelly.core.contracts import ExecutionAdapter, ExecutionMode, ExecutionRequest, ExecutionResult, FailureCode, StepStatus
from gracekelly.core.models import models_equivalent


class PerplexityBrowserAdapter(ExecutionAdapter):
    name = "browser.perplexity"

    def __init__(
        self,
        *,
        session_manager: BrowserSessionManager,
        automation: BrowserAutomationPort | None = None,
        popup_policy: PopupPolicy | None = None,
        auth_recovery_policy: AuthRecoveryPolicy | None = None,
        model_verification_policy: ModelVerificationPolicy | None = None,
        submit_policy: SubmitPolicy | None = None,
    ) -> None:
        self._session_manager = session_manager
        self._automation = automation or NullBrowserAutomation()
        self._popup_policy = popup_policy or PopupPolicy()
        self._auth_policy = auth_recovery_policy or AuthRecoveryPolicy()
        self._model_policy = model_verification_policy or ModelVerificationPolicy()
        self._submit_policy = submit_policy or SubmitPolicy()

    def execute(self, request: ExecutionRequest) -> ExecutionResult:
        model = request.step.model
        if request.cancellation and request.cancellation.is_cancelled:
            return self._cancelled(model.id, model.display_name)
        if not self._session_manager.state.configured:
            return self._failure(
                model.id,
                model.display_name,
                FailureCode.PROVIDER_UNAVAILABLE,
                "Browser session is not configured yet.",
            )

        try:
            self._automation.ensure_session(self._session_manager)
            self._session_manager.mark_active()
            self._automation.dismiss_popups(self._popup_policy)
            auth = self._ensure_auth()
            if not auth.logged_in:
                return self._failure(
                    model.id,
                    model.display_name,
                    FailureCode.AUTH_FAILED,
                    auth.reason or "Browser session is not authenticated.",
                )

            selection = self._automation.select_model(
                provider_model_id=model.provider_model_id,
                policy=self._model_policy,
            )
            if not self._model_matches_expected(model.provider_model_id, selection.actual_label):
                return self._failure(
                    model.id,
                    model.display_name,
                    FailureCode.MODEL_MISMATCH,
                    (
                        f"Requested browser model '{model.provider_model_id}' "
                        f"but UI shows '{selection.actual_label}'."
                    ),
                    extra_details={
                        "requested_label": selection.requested_label,
                        "actual_label": selection.actual_label,
                    },
                )

            if request.cancellation and request.cancellation.is_cancelled:
                return self._cancelled(model.id, model.display_name)

            output = self._automation.submit_prompt(
                prompt=request.prompt,
                policy=self._submit_policy,
                timeout_seconds=model.timeout_seconds,
            )
            if request.cancellation and request.cancellation.is_cancelled and not output.output_text.strip():
                return self._cancelled(model.id, model.display_name)
            return ExecutionResult(
                adapter_name=self.name,
                model_id=model.id,
                model_display_name=model.display_name,
                execution_mode=ExecutionMode.BROWSER,
                status=StepStatus.COMPLETED,
                output_text=output.output_text.strip(),
                details={
                    "provider": "perplexity",
                    "requested_model_label": selection.requested_label,
                    "actual_model_label": selection.actual_label,
                    **selection.details,
                    **output.details,
                },
            )
        except TimeoutError:
            return self._failure(
                model.id,
                model.display_name,
                FailureCode.TIMEOUT,
                f"Browser execution timed out after {model.timeout_seconds}s.",
            )
        except NotImplementedError as exc:
            return self._failure(
                model.id,
                model.display_name,
                FailureCode.PROVIDER_UNAVAILABLE,
                str(exc),
            )
        except Exception as exc:
            return self._failure(
                model.id,
                model.display_name,
                FailureCode.UNKNOWN_ERROR,
                f"Browser execution failed: {exc}",
            )

    def healthcheck(self) -> dict[str, object]:
        session_health = self._session_manager.healthcheck()
        automation_health = self._automation.healthcheck()
        status = session_health["status"]
        if automation_health.get("status") == "failed":
            status = "failed"
        elif automation_health.get("status") == "degraded" and status == "ok":
            status = "degraded"
        return {
            "status": status,
            "adapter_name": self.name,
            "provider": "perplexity",
            "session": session_health,
            "automation": automation_health,
            "policies": {
                "popup": asdict(self._popup_policy),
                "auth_recovery": asdict(self._auth_policy),
                "model_verification": asdict(self._model_policy),
                "submit": asdict(self._submit_policy),
            },
        }

    def _ensure_auth(self) -> BrowserAuthStatus:
        auth = self._automation.auth_status(self._auth_policy)
        if auth.logged_in:
            return auth
        if self._auth_policy.allow_relogin:
            return self._automation.recover_auth(self._auth_policy)
        return auth

    def _model_matches_expected(self, requested_label: str, actual_label: str) -> bool:
        if requested_label == actual_label:
            return True
        if not self._model_policy.allow_alias_match:
            return False
        return models_equivalent(requested_label, actual_label)

    def _cancelled(self, model_id: str, model_display_name: str) -> ExecutionResult:
        return ExecutionResult(
            adapter_name=self.name,
            model_id=model_id,
            model_display_name=model_display_name,
            execution_mode=ExecutionMode.BROWSER,
            status=StepStatus.CANCELLED,
            details={
                "provider": "perplexity",
                "cancelled": True,
            },
        )

    def _failure(
        self,
        model_id: str,
        model_display_name: str,
        failure_code: FailureCode,
        message: str,
        *,
        extra_details: dict[str, object] | None = None,
    ) -> ExecutionResult:
        self._session_manager.mark_error(message)
        details = {
            "provider": "perplexity",
            "configured": self._session_manager.state.configured,
            "active": self._session_manager.state.active,
        }
        if extra_details:
            details.update(extra_details)
        return ExecutionResult(
            adapter_name=self.name,
            model_id=model_id,
            model_display_name=model_display_name,
            execution_mode=ExecutionMode.BROWSER,
            status=StepStatus.FAILED,
            failure_code=failure_code,
            failure_message=message,
            details=details,
        )
