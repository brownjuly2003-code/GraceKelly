from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
import logging
import time
from typing import Any, Callable

from gracekelly.adapters.browser.automation import (
    BrowserAuthStatus,
    BrowserAutomationPort,
    BrowserExecutionOutput,
    BrowserModelSelection,
    BrowserProfileBusyError,
)
from gracekelly.adapters.browser.policy import (
    AuthRecoveryPolicy,
    ModelVerificationPolicy,
    PopupPolicy,
    SubmitPolicy,
)
from gracekelly.adapters.browser.selectors import PerplexitySelectors
from gracekelly.adapters.browser.session import BrowserSessionManager

logger = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class PlaywrightBrowserRuntimeConfig:
    channel: str = "chrome"
    headless: bool = False
    action_timeout_ms: int = 5_000
    poll_interval_seconds: float = 0.5
    launch_args: tuple[str, ...] = field(
        default_factory=lambda: ("--disable-blink-features=AutomationControlled",)
    )


class PlaywrightBrowserAutomation(BrowserAutomationPort):
    def __init__(
        self,
        *,
        selectors: PerplexitySelectors | None = None,
        runtime: PlaywrightBrowserRuntimeConfig | None = None,
        sync_playwright_factory: Callable[[], Any] | None = None,
    ) -> None:
        self._selectors = selectors or PerplexitySelectors()
        self._runtime = runtime or PlaywrightBrowserRuntimeConfig()
        self._sync_playwright_factory = sync_playwright_factory
        self._playwright_manager: Any | None = None
        self._playwright: Any | None = None
        self._context: Any | None = None
        self._page: Any | None = None
        self._observed_model_menu: tuple[str, ...] = ()
        self._observed_model_menu_at: datetime | None = None

    def ensure_session(self, session_manager: BrowserSessionManager) -> None:
        state = session_manager.state
        if not state.configured:
            raise NotImplementedError("Browser session is not configured yet.")
        if self._page is not None:
            is_closed = getattr(self._page, "is_closed", None)
            if callable(is_closed) and not is_closed():
                return

        logger.info(
            "Launching Playwright browser session for provider %s using profile %s",
            state.provider,
            state.profile_dir,
        )
        manager = None
        playwright = None
        context = None
        try:
            manager = self._build_playwright_manager()
            playwright = manager.start()
            context = playwright.chromium.launch_persistent_context(
                state.profile_dir,
                channel=self._runtime.channel,
                headless=self._runtime.headless,
                args=list(self._runtime.launch_args),
            )
            page = context.new_page()
            page.set_default_timeout(self._runtime.action_timeout_ms)
            page.goto(state.base_url, wait_until="domcontentloaded")
        except Exception as exc:
            if context is not None:
                context.close()
            if playwright is not None:
                playwright.stop()
            if self._is_profile_busy_error(exc):
                raise BrowserProfileBusyError(
                    f"Browser profile directory '{state.profile_dir}' is already in use by another Chrome process."
                ) from exc
            raise

        self._playwright_manager = manager
        self._playwright = playwright
        self._context = context
        self._page = page
        self._wait_for_shell()

    def dismiss_popups(self, policy: PopupPolicy) -> None:
        page = self._page_or_raise()
        for button_name in self._selectors.cookie_button_names:
            locator = page.get_by_role("button", name=button_name)
            if self._locator_is_visible(locator):
                logger.info("Dismissing browser popup via button '%s'", button_name)
                locator.click()
                return

        for _ in range(policy.escape_key_retries):
            page.keyboard.press("Escape")

    def auth_status(self, policy: AuthRecoveryPolicy) -> BrowserAuthStatus:
        page = self._page_or_raise()
        body_text = self._body_text(page)
        prompt_input_visible = self._locator_is_visible(page.locator(self._selectors.prompt_input))
        return self._infer_auth_status(
            body_text=body_text,
            prompt_input_visible=prompt_input_visible,
            policy=policy,
        )

    def recover_auth(self, policy: AuthRecoveryPolicy) -> BrowserAuthStatus:
        return self.auth_status(policy)

    def select_model(
        self,
        *,
        provider_model_id: str,
        policy: ModelVerificationPolicy,
    ) -> BrowserModelSelection:
        page = self._page_or_raise()
        model_button = self._resolve_model_button(page, attempts=policy.wait_attempts)
        reset_attempted = False
        visible_buttons = self._button_debug_snapshot(page)
        if model_button is None:
            reset_attempted = self._reset_to_new_thread(page)
            visible_buttons = self._button_debug_snapshot(page)
        if model_button is None and reset_attempted:
            model_button = self._resolve_model_button(page, attempts=policy.wait_attempts)
        if model_button is None:
            raise RuntimeError(
                "Perplexity model selector did not become visible after shell readiness. "
                f"fresh_thread_reset_attempted={reset_attempted}. "
                f"Visible buttons: {visible_buttons}"
            )
        model_button_text_before = self._locator_inner_text(model_button)
        logger.info("Selecting Perplexity model '%s' through Playwright", provider_model_id)
        model_button.click()
        menu_texts = self._model_menu_texts(page)
        self._record_model_menu_snapshot(menu_texts)

        option = self._first_visible_locator(
            (
                page.get_by_role("button", name=provider_model_id),
                page.get_by_role("option", name=provider_model_id),
                page.get_by_text(provider_model_id, exact=True),
            )
        )
        if option is None:
            actual_label = self._infer_active_model_label(menu_texts)
            logger.warning(
                "Perplexity model option '%s' was not found; current menu appears to start with '%s'.",
                provider_model_id,
                actual_label or "unknown",
            )
            return BrowserModelSelection(
                requested_label=provider_model_id,
                actual_label=actual_label or provider_model_id,
                details={
                    "driver": "playwright",
                    "model_selection_verified": False,
                    "model_selection_attempted": False,
                    "model_verification_wait_attempts": policy.wait_attempts,
                    "model_button_text_before": model_button_text_before,
                    "model_button_text_after": model_button_text_before,
                    "button_debug_snapshot": self._button_debug_snapshot(page),
                    "model_menu_snapshot": menu_texts,
                },
            )

        option.click()
        time.sleep(self._runtime.poll_interval_seconds)
        model_button_text_after = self._locator_inner_text(model_button)
        selection_evidence = self._selection_evidence(option)
        model_selection_verified = False
        if policy.verify_button_label:
            model_selection_verified = self._button_text_matches_requested(provider_model_id, model_button_text_after)
        if not model_selection_verified and selection_evidence["verified"]:
            model_selection_verified = True
        return BrowserModelSelection(
            requested_label=provider_model_id,
            actual_label=provider_model_id,
            details={
                "driver": "playwright",
                "model_selection_verified": model_selection_verified,
                "model_selection_attempted": True,
                "model_verification_wait_attempts": policy.wait_attempts,
                "model_button_text_before": model_button_text_before,
                "model_button_text_after": model_button_text_after,
                "selection_indicator": selection_evidence["indicator"],
                "selection_indicator_value": selection_evidence["indicator_value"],
                "button_debug_snapshot": self._button_debug_snapshot(page),
                "model_menu_snapshot": menu_texts,
            },
        )

    def submit_prompt(
        self,
        *,
        prompt: str,
        policy: SubmitPolicy,
        timeout_seconds: int,
    ) -> BrowserExecutionOutput:
        page = self._page_or_raise()
        prompt_input = page.locator(self._selectors.prompt_input)
        if not self._locator_is_visible(prompt_input):
            raise RuntimeError("Perplexity prompt input is not visible.")

        logger.info("Submitting prompt through Playwright (timeout=%ss)", timeout_seconds)
        prompt_input.click(force=True)
        self._clear_prompt_input(page)
        self._fill_prompt_input(page, prompt)
        self._click_submit(page, policy)
        output_text = self._wait_for_response_text(
            page=page,
            prompt=prompt,
            timeout_seconds=timeout_seconds,
        )
        return BrowserExecutionOutput(
            output_text=output_text["text"],
            details={
                "driver": "playwright",
                "submitted_prompt": prompt,
                "timeout_seconds": timeout_seconds,
                "response_source": output_text["source"],
                "response_candidate_counts": output_text["candidate_counts"],
            },
        )

    def healthcheck(self) -> dict[str, object]:
        dependency_error = self._playwright_dependency_error()
        return {
            "status": "ok" if dependency_error is None else "degraded",
            "implemented": dependency_error is None,
            "driver": "playwright",
            "channel": self._runtime.channel,
            "headless": self._runtime.headless,
            "launched": self._page is not None,
            "observed_model_menu": list(self._observed_model_menu),
            "observed_model_menu_at": self._observed_model_menu_at,
            "observed_model_menu_source": "perplexity-model-menu" if self._observed_model_menu else None,
            "reason": dependency_error,
        }

    def close(self) -> None:
        context = self._context
        playwright = self._playwright
        self._page = None
        self._context = None
        self._playwright = None
        self._playwright_manager = None
        if context is not None:
            context.close()
        if playwright is not None:
            playwright.stop()

    def _build_playwright_manager(self) -> Any:
        factory = self._sync_playwright_factory
        if factory is not None:
            return factory()
        try:
            from playwright.sync_api import sync_playwright
        except ModuleNotFoundError as exc:  # pragma: no cover
            raise NotImplementedError("playwright is required for the 'playwright' browser backend.") from exc
        return sync_playwright()

    def _playwright_dependency_error(self) -> str | None:
        if self._sync_playwright_factory is not None:
            return None
        try:
            from playwright.sync_api import sync_playwright  # noqa: F401
        except ModuleNotFoundError:
            return "playwright is not installed."
        return None

    def _page_or_raise(self) -> Any:
        if self._page is None:
            raise RuntimeError("Browser session has not been initialized.")
        return self._page

    def _is_profile_busy_error(self, exc: Exception) -> bool:
        message = str(exc)
        return (
            "launch_persistent_context" in message
            and "Target page, context or browser has been closed" in message
            and "exitCode=21" in message
        )

    def _wait_for_shell(self) -> None:
        page = self._page_or_raise()
        deadline = time.monotonic() + 10
        while time.monotonic() < deadline:
            body_text = self._body_text(page)
            if self._locator_is_visible(page.locator(self._selectors.prompt_input)):
                return
            if any(marker in body_text for marker in self._selectors.signed_out_markers):
                return
            if all(marker in body_text for marker in self._selectors.ready_markers[:2]):
                return
            time.sleep(self._runtime.poll_interval_seconds)
        raise TimeoutError("Perplexity shell did not become ready.")

    def _clear_prompt_input(self, page: Any) -> None:
        page.keyboard.press("ControlOrMeta+A")
        page.keyboard.press("Backspace")

    def _fill_prompt_input(self, page: Any, prompt: str) -> None:
        prompt_input = page.locator(self._selectors.prompt_input)
        try:
            prompt_input.fill(prompt)
            return
        except Exception:
            pass

        try:
            prompt_input.press_sequentially(prompt)
            return
        except Exception:
            pass

        page.evaluate(
            """
            ([selector, value]) => {
              const input = document.querySelector(selector);
              if (!input) {
                return false;
              }
              input.focus();
              input.innerText = value;
              input.dispatchEvent(new InputEvent("input", { bubbles: true, data: value }));
              return true;
            }
            """,
            [self._selectors.prompt_input, prompt],
        )

    def _click_submit(self, page: Any, policy: SubmitPolicy) -> None:
        for _ in range(policy.click_attempts):
            if self._body_has_signed_out_marker(page):
                raise PermissionError("Perplexity sign-in overlay blocked prompt submission.")
            submit = page.locator(self._selectors.submit_button)
            if self._locator_is_visible(submit):
                try:
                    submit.click()
                except Exception as exc:
                    if self._body_has_signed_out_marker(page):
                        raise PermissionError("Perplexity sign-in overlay blocked prompt submission.") from exc
                    time.sleep(self._runtime.poll_interval_seconds)
                    continue
                return
            time.sleep(self._runtime.poll_interval_seconds)

        if policy.allow_js_fallback:
            if self._body_has_signed_out_marker(page):
                raise PermissionError("Perplexity sign-in overlay blocked prompt submission.")
            clicked = page.evaluate(
                """
                (selector) => {
                  const button = document.querySelector(selector);
                  if (!button) {
                    return false;
                  }
                  button.click();
                  return true;
                }
                """,
                self._selectors.submit_button,
            )
            if clicked:
                return

        page.keyboard.press("Control+Enter")

    def _body_has_signed_out_marker(self, page: Any) -> bool:
        body_text = self._body_text(page)
        return any(marker in body_text for marker in self._selectors.signed_out_markers)

    def _model_menu_texts(self, page: Any) -> list[str]:
        texts: list[str] = []
        for selector in self._selectors.model_menu_candidates:
            try:
                texts.extend(page.locator(selector).all_inner_texts())
            except Exception:
                continue
        return [text for text in texts if text.strip()]

    def _record_model_menu_snapshot(self, menu_texts: list[str]) -> None:
        observed_lines: list[str] = []
        for block in menu_texts:
            for line in block.splitlines():
                normalized = line.strip()
                if normalized and normalized not in observed_lines:
                    observed_lines.append(normalized)
        if not observed_lines:
            return
        self._observed_model_menu = tuple(observed_lines)
        self._observed_model_menu_at = datetime.now(UTC)

    def _infer_active_model_label(self, menu_texts: list[str]) -> str | None:
        for block in menu_texts:
            for line in block.splitlines():
                normalized = line.strip()
                if normalized:
                    return normalized
        return None

    def _wait_for_response_text(self, *, page: Any, prompt: str, timeout_seconds: int) -> dict[str, Any]:
        deadline = time.monotonic() + timeout_seconds
        while time.monotonic() < deadline:
            candidate_texts = self._collect_response_candidates(page=page, prompt=prompt)
            response_text = self._pick_response_text(prompt=prompt, candidate_texts=candidate_texts)
            if response_text is not None:
                return response_text
            time.sleep(self._runtime.poll_interval_seconds)
        raise TimeoutError(f"Perplexity did not return a response within {timeout_seconds}s.")

    def _collect_response_candidates(self, *, page: Any, prompt: str) -> list[tuple[str, str]]:
        candidates: list[tuple[str, str]] = []
        for selector in self._selectors.response_candidates:
            locator = page.locator(selector)
            for text in self._locator_texts(locator):
                candidates.append((selector, text))

        body_text = self._body_text(page)
        if prompt in body_text:
            candidates.append(("body_after_prompt", body_text.split(prompt, 1)[1]))
        else:
            candidates.append(("body", body_text))
        return candidates

    def _infer_auth_status(
        self,
        *,
        body_text: str,
        prompt_input_visible: bool,
        policy: AuthRecoveryPolicy,
    ) -> BrowserAuthStatus:
        for marker in self._selectors.signed_out_markers:
            if marker in body_text:
                return BrowserAuthStatus(
                    logged_in=False,
                    reason="Sign-in prompt is visible in the Perplexity UI.",
                )
        if prompt_input_visible:
            return BrowserAuthStatus(logged_in=True)
        if policy.treat_unknown_login_state_as_logged_out:
            return BrowserAuthStatus(
                logged_in=False,
                reason="Unable to determine browser login state from the current page.",
            )
        return BrowserAuthStatus(logged_in=True)

    def _pick_response_text(self, *, prompt: str, candidate_texts: list[tuple[str, str]]) -> dict[str, Any] | None:
        cleaned_candidates: list[tuple[str, str]] = []
        candidate_counts: dict[str, int] = {}
        for source, candidate in candidate_texts:
            candidate_counts[source] = candidate_counts.get(source, 0) + 1
            cleaned = self._clean_candidate_text(prompt=prompt, candidate=candidate)
            if cleaned:
                cleaned_candidates.append((source, cleaned))
        if not cleaned_candidates:
            return None
        source, text = max(cleaned_candidates, key=lambda item: len(item[1]))
        return {
            "text": text,
            "source": source,
            "candidate_counts": candidate_counts,
        }

    def _clean_candidate_text(self, *, prompt: str, candidate: str) -> str | None:
        normalized = " ".join(candidate.split())
        if not normalized:
            return None
        if prompt in normalized:
            normalized = normalized.split(prompt, 1)[1].strip()
        if not normalized:
            return None
        stripped_lines = self._strip_shell_noise(normalized)
        if not stripped_lines:
            return None
        return stripped_lines

    def _strip_shell_noise(self, value: str) -> str:
        lines = [line.strip() for line in value.splitlines() if line.strip()]
        if not lines:
            lines = [part.strip() for part in value.split("  ") if part.strip()]
        filtered = [line for line in lines if line not in self._selectors.shell_noise_lines]
        if not filtered:
            return ""
        return "\n".join(filtered).strip()

    def _first_visible_locator(self, locators: tuple[Any, ...]) -> Any | None:
        for locator in locators:
            if self._locator_is_visible(locator):
                return getattr(locator, "first", locator)
        return None

    def _resolve_model_button(self, page: Any, *, attempts: int) -> Any | None:
        locators = (page.locator(self._selectors.model_button),)
        for _ in range(max(attempts, 1)):
            button = self._first_visible_locator(locators)
            if button is not None:
                return button
            time.sleep(self._runtime.poll_interval_seconds)
        return None

    def _reset_to_new_thread(self, page: Any) -> bool:
        button = self._first_visible_locator(
            tuple(page.locator(f'button:has-text("{name}")') for name in self._selectors.new_thread_button_names)
            + tuple(page.get_by_role("button", name=name) for name in self._selectors.new_thread_button_names)
            + tuple(page.get_by_text(name) for name in self._selectors.new_thread_button_names)
        )
        if button is None:
            return False
        logger.info("Resetting Perplexity UI to a fresh thread before model selection.")
        button.click()
        time.sleep(self._runtime.poll_interval_seconds)
        if self._first_visible_locator(
            tuple(page.locator(f'button:has-text("{name}")') for name in self._selectors.new_thread_button_names)
        ):
            page.keyboard.press("Control+I")
            time.sleep(self._runtime.poll_interval_seconds)
        self._wait_for_shell()
        return True

    def _locator_is_visible(self, locator: Any) -> bool:
        candidate = getattr(locator, "first", locator)
        is_visible = getattr(candidate, "is_visible", None)
        if callable(is_visible):
            try:
                return bool(is_visible())
            except Exception:
                return False
        count = getattr(candidate, "count", None)
        if callable(count):
            try:
                return bool(count())
            except Exception:
                return False
        return False

    def _locator_texts(self, locator: Any) -> list[str]:
        candidate = getattr(locator, "first", locator)
        try:
            if candidate.count() == 0:
                return []
        except Exception:
            pass

        try:
            return [text for text in candidate.all_inner_texts() if text.strip()]
        except Exception:
            pass

        try:
            text = candidate.inner_text()
        except Exception:
            return []
        return [text] if text.strip() else []

    def _locator_inner_text(self, locator: Any) -> str | None:
        candidate = getattr(locator, "first", locator)
        try:
            text = candidate.inner_text()
        except Exception:
            return None
        stripped = text.strip()
        return stripped or None

    def _selection_evidence(self, locator: Any) -> dict[str, Any]:
        candidate = getattr(locator, "first", locator)
        for attribute, expected_values in (
            ("aria-selected", {"true"}),
            ("aria-checked", {"true"}),
            ("data-selected", {"true"}),
            ("data-state", {"checked", "selected", "active"}),
        ):
            value = self._locator_attribute(candidate, attribute)
            if value is None:
                continue
            normalized = value.strip().lower()
            if normalized in expected_values:
                return {
                    "verified": True,
                    "indicator": attribute,
                    "indicator_value": value,
                }
        return {
            "verified": False,
            "indicator": None,
            "indicator_value": None,
        }

    def _locator_attribute(self, locator: Any, name: str) -> str | None:
        try:
            value = locator.get_attribute(name)
        except Exception:
            return None
        return value if value is not None else None

    def _button_text_matches_requested(self, requested_label: str, button_text: str | None) -> bool:
        if not button_text:
            return False
        return requested_label in button_text

    def _button_debug_snapshot(self, page: Any) -> list[str]:
        try:
            entries = page.evaluate(
                """
                () => Array.from(document.querySelectorAll('button')).slice(0, 16).map((button) => {
                  const ariaLabel = button.getAttribute('aria-label');
                  const text = (button.innerText || '').trim();
                  return ariaLabel ? `${ariaLabel}::${text}` : text;
                })
                """
            )
        except Exception:
            return []
        if not isinstance(entries, list):
            return []
        return [str(entry).strip() for entry in entries if str(entry).strip()]

    def _body_text(self, page: Any) -> str:
        try:
            return page.inner_text("body")
        except Exception:
            return ""
