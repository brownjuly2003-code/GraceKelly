from __future__ import annotations

import inspect
import logging
import time
from dataclasses import asdict

from gracekelly.adapters.browser.automation import (
    BrowserAuthStatus,
    BrowserAutomationPort,
    BrowserProfileBusyError,
    NullBrowserAutomation,
)
from gracekelly.adapters.browser.policy import (
    AuthRecoveryPolicy,
    ModelVerificationPolicy,
    PopupPolicy,
    SubmitPolicy,
)
from gracekelly.adapters.browser.session import BrowserSessionManager
from gracekelly.core.contracts import (
    ExecutionAdapter,
    ExecutionMode,
    ExecutionRequest,
    ExecutionResult,
    FailureCode,
    StepStatus,
)
from gracekelly.core.models import models_equivalent

logger = logging.getLogger(__name__)


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
        self._automation: BrowserAutomationPort = automation or NullBrowserAutomation()
        self._popup_policy = popup_policy or PopupPolicy()
        self._auth_policy = auth_recovery_policy or AuthRecoveryPolicy()
        self._model_policy = model_verification_policy or ModelVerificationPolicy()
        self._submit_policy = submit_policy or SubmitPolicy()

    @property
    def session_manager(self) -> BrowserSessionManager:
        return self._session_manager

    @property
    def automation(self) -> BrowserAutomationPort:
        return self._automation

    @automation.setter
    def automation(self, value: BrowserAutomationPort) -> None:
        self._automation = value

    def execute(self, request: ExecutionRequest) -> ExecutionResult:
        model = request.step.model
        t0 = time.monotonic()
        if request.attachments:
            logger.warning("Browser adapter ignores image attachments (not supported yet)")
        logger.info(
            "Browser execution started for task %s model %s provider %s",
            request.task_id,
            model.id,
            model.provider,
        )
        if request.cancellation and request.cancellation.is_cancelled:
            return self._cancelled(model.id, model.display_name)
        if not self._session_manager.state.configured:
            return self._failure(
                task_id=request.task_id,
                model_id=model.id,
                model_display_name=model.display_name,
                failure_code=FailureCode.PROVIDER_UNAVAILABLE,
                message="Browser session is not configured yet.",
            )

        try:
            self._automation.ensure_session(self._session_manager)
            self._session_manager.mark_active()
            self._automation.dismiss_popups(self._popup_policy)
            auth = self._ensure_auth()
            logger.info(
                "Browser auth check for task %s: logged_in=%s",
                request.task_id,
                auth.logged_in,
            )
            if not auth.logged_in:
                return self._failure(
                    task_id=request.task_id,
                    model_id=model.id,
                    model_display_name=model.display_name,
                    failure_code=FailureCode.AUTH_FAILED,
                    message=auth.reason or "Browser session is not authenticated.",
                )

            selection = self._automation.select_model(
                provider_model_id=model.provider_model_id,
                policy=self._model_policy,
            )
            if not self._model_matches_expected(model.provider_model_id, selection.actual_label):
                return self._failure(
                    task_id=request.task_id,
                    model_id=model.id,
                    model_display_name=model.display_name,
                    failure_code=FailureCode.MODEL_MISMATCH,
                    message=(
                        f"Requested browser model '{model.provider_model_id}' "
                        f"but UI shows '{selection.actual_label}'."
                    ),
                    extra_details={
                        "requested_label": selection.requested_label,
                        "actual_label": selection.actual_label,
                    },
                )

            thinking_enabled = False
            if model.reasoning_capable:
                enable_thinking_fn = getattr(self._automation, "enable_thinking", None)
                if callable(enable_thinking_fn):
                    thinking_enabled = enable_thinking_fn()
                    logger.info("Thinking toggle for model %s: %s", model.id, thinking_enabled)

            if request.cancellation and request.cancellation.is_cancelled:
                return self._cancelled(model.id, model.display_name)

            output = self._automation.submit_prompt(
                prompt=request.prompt,
                policy=self._submit_policy,
                timeout_seconds=model.timeout_seconds,
            )
            if request.cancellation and request.cancellation.is_cancelled and not output.output_text.strip():
                return self._cancelled(model.id, model.display_name)
            elapsed_ms = int((time.monotonic() - t0) * 1000)
            logger.info(
                "Browser execution completed for task %s model %s provider %s "
                "duration_ms=%d response_source=%s model_verified=%s",
                request.task_id,
                model.id,
                model.provider,
                elapsed_ms,
                output.details.get("response_source", "unknown"),
                selection.details.get("model_selection_verified", False),
            )
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
                    "thinking_enabled": thinking_enabled,
                    **selection.details,
                    **output.details,
                },
            )
        except TimeoutError:
            return self._failure(
                task_id=request.task_id,
                model_id=model.id,
                model_display_name=model.display_name,
                failure_code=FailureCode.TIMEOUT,
                message=f"Browser execution timed out after {model.timeout_seconds}s.",
            )
        except PermissionError as exc:
            return self._failure(
                task_id=request.task_id,
                model_id=model.id,
                model_display_name=model.display_name,
                failure_code=FailureCode.AUTH_FAILED,
                message=str(exc) or "Browser session is not authenticated.",
            )
        except BrowserProfileBusyError as exc:
            return self._failure(
                task_id=request.task_id,
                model_id=model.id,
                model_display_name=model.display_name,
                failure_code=FailureCode.PROVIDER_UNAVAILABLE,
                message=str(exc),
            )
        except NotImplementedError as exc:
            return self._failure(
                task_id=request.task_id,
                model_id=model.id,
                model_display_name=model.display_name,
                failure_code=FailureCode.PROVIDER_UNAVAILABLE,
                message=str(exc),
            )
        except Exception as exc:
            return self._failure(
                task_id=request.task_id,
                model_id=model.id,
                model_display_name=model.display_name,
                failure_code=FailureCode.UNKNOWN_ERROR,
                message=f"Browser execution failed: {exc}",
            )

    def healthcheck(self) -> dict[str, object]:
        session_health = self._session_manager.healthcheck()
        automation_health = self._automation.healthcheck()
        status = session_health["status"]
        runtime_consistent = True
        automation_launched = automation_health.get("launched")
        if isinstance(automation_launched, bool) and session_health.get("active") != automation_launched:
            runtime_consistent = False
            status = "degraded"
        if automation_health.get("status") == "failed":
            status = "failed"
        elif automation_health.get("status") == "degraded" and status == "ok":
            status = "degraded"
        return {
            "status": status,
            "adapter_name": self.name,
            "provider": "perplexity",
            "runtime_consistent": runtime_consistent,
            "session": session_health,
            "automation": automation_health,
            "policies": {
                "popup": asdict(self._popup_policy),
                "auth_recovery": asdict(self._auth_policy),
                "model_verification": asdict(self._model_policy),
                "submit": asdict(self._submit_policy),
            },
        }

    async def close(self) -> None:
        close_method = getattr(self._automation, "close", None)
        if callable(close_method):
            result = close_method()
            if inspect.isawaitable(result):
                await result
        self._session_manager.mark_idle()

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
        task_id: str,
        model_id: str,
        model_display_name: str,
        failure_code: FailureCode,
        message: str,
        *,
        extra_details: dict[str, object] | None = None,
    ) -> ExecutionResult:
        self._session_manager.mark_error(message)
        session_state = self._session_manager.state
        logger.warning(
            "Browser execution failed for task %s model %s code=%s: %s",
            task_id,
            model_id,
            failure_code.value,
            message,
        )

        details = {
            "provider": "perplexity",
            "configured": session_state.configured,
            "active": session_state.active,
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
