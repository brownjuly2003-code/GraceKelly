from __future__ import annotations

import logging
import os
import re
import tempfile
import threading
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

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
from gracekelly.core.contracts import FileAttachment

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
    screenshots_dir: str | None = None


_PROFILE_LOCK_MARKERS: tuple[str, ...] = ("SingletonLock", "SingletonSocket", "SingletonCookie")


def _profile_is_locked(profile_dir: str) -> str | None:
    """Return lock marker path if another Chrome instance holds this profile, else None."""
    profile_path = Path(profile_dir)
    if not profile_path.exists():
        return None
    for marker in _PROFILE_LOCK_MARKERS:
        candidate = profile_path / marker
        if candidate.exists():
            return str(candidate)
    return None


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
        self._base_url: str | None = None
        self._session_thread_id: int | None = None
        self._observed_model_menu: tuple[str, ...] = ()
        self._observed_model_menu_at: datetime | None = None
        self._verified_model_labels_at: dict[str, datetime] = {}
        self._last_model_picker_unavailable_at: datetime | None = None

    def inspect_model_catalog(self) -> tuple[str, ...]:
        page = self._page_or_raise()
        model_button = self._resolve_model_button(page, attempts=3)
        if model_button is None and self._navigate_home_for_model_selection(page):
            model_button = self._resolve_model_button(page, attempts=3)
        if model_button is None and self._reset_to_new_thread(page):
            model_button = self._resolve_model_button(page, attempts=3)
        if model_button is None:
            self._last_model_picker_unavailable_at = datetime.now(UTC)
            raise RuntimeError("Perplexity model picker is unavailable.")
        if self._body_has_signed_out_marker(page):
            raise PermissionError("Perplexity sign-in overlay blocked model catalog inspection.")

        try:
            model_button.click()
        except Exception as exc:
            if self._body_has_signed_out_marker(page):
                raise PermissionError("Perplexity sign-in overlay blocked model catalog inspection.") from exc
            raise
        time.sleep(self._runtime.poll_interval_seconds)
        menu_texts = self._model_menu_texts(page)
        self._record_model_menu_snapshot(menu_texts)
        labels = self._extract_catalog_labels(menu_texts)
        page.keyboard.press("Escape")
        if not labels:
            raise RuntimeError("Unable to extract browser model labels from Perplexity menu.")
        return tuple(labels)

    def ensure_session(self, session_manager: BrowserSessionManager) -> None:
        state = session_manager.state
        if not state.configured:
            raise NotImplementedError("Browser session is not configured yet.")
        self._base_url = state.base_url
        current_thread_id = threading.get_ident()
        if self._page is not None:
            is_closed = getattr(self._page, "is_closed", None)
            if callable(is_closed) and not is_closed():
                if self._session_thread_id in (None, current_thread_id):
                    logger.debug("Reusing existing Playwright browser session")
                    return
                logger.warning(
                    "Discarding Playwright browser session created on thread %s before reopening on thread %s",
                    self._session_thread_id,
                    current_thread_id,
                )
                self._clear_runtime_handles()

        if state.profile_dir is not None:
            lock_marker = _profile_is_locked(state.profile_dir)
            if lock_marker is not None:
                raise BrowserProfileBusyError(
                    f"Browser profile directory '{state.profile_dir}' is locked by another Chrome "
                    f"process (marker: {lock_marker}). Close Chrome or use a dedicated "
                    f"GRACEKELLY_BROWSER_PROFILE_DIR that is never opened by a regular Chrome window."
                )

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
        self._session_thread_id = current_thread_id
        self._wait_for_shell()
        self._screenshot("01-session-ready")

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

    def reset_page_state(self) -> bool:
        # Subsequent execute() calls on the same adapter reuse the Perplexity page;
        # without an explicit reset the page is still on the previous thread URL,
        # so body_after_prompt extraction can match the prior answer. Always route
        # back to the home ask-input before a new run. Idempotent on the home page.
        page = self._page
        if page is None:
            return False
        return self._navigate_home_for_model_selection(page)

    def auth_status(self, policy: AuthRecoveryPolicy) -> BrowserAuthStatus:
        page = self._page_or_raise()
        body_text = self._body_text(page)
        prompt_input_visible = self._locator_is_visible(page.locator(self._selectors.prompt_input))
        signed_out_visible = any(marker in body_text for marker in self._selectors.signed_out_markers)
        # Perplexity briefly hides the home ask-input after a response lands (navigation to
        # thread URL). Without a settle, back-to-back sub-execs in smart decomposition hit
        # "unknown login state" and degrade to [auth_failed]. _wait_for_shell polls up to 10s
        # for prompt_input visibility; bounded, no effect on real logouts.
        if not signed_out_visible and not prompt_input_visible:
            try:
                self._wait_for_shell()
            except TimeoutError:
                pass
            body_text = self._body_text(page)
            prompt_input_visible = self._locator_is_visible(page.locator(self._selectors.prompt_input))
        status = self._infer_auth_status(
            body_text=body_text,
            prompt_input_visible=prompt_input_visible,
            policy=policy,
        )
        if not status.logged_in:
            self._log_auth_unknown_diagnostics(
                page=page,
                body_text=body_text,
                prompt_input_visible=prompt_input_visible,
            )
        self._screenshot("02-auth-logged-in" if status.logged_in else "02-auth-signed-out")
        return status

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
        home_navigation_attempted = False
        reset_attempted = False
        visible_buttons = self._button_debug_snapshot(page)
        if model_button is None:
            home_navigation_attempted = self._navigate_home_for_model_selection(page)
            if home_navigation_attempted:
                visible_buttons = self._button_debug_snapshot(page)
                model_button = self._resolve_model_button(page, attempts=policy.wait_attempts)
        if model_button is None:
            reset_attempted = self._reset_to_new_thread(page)
            visible_buttons = self._button_debug_snapshot(page)
        if model_button is None and reset_attempted:
            model_button = self._resolve_model_button(page, attempts=policy.wait_attempts)
        if model_button is None:
            self._last_model_picker_unavailable_at = datetime.now(UTC)
            logger.warning(
                "Perplexity model selector is unavailable; continuing without verified model selection. "
                "fresh_thread_reset_attempted=%s visible_buttons=%s",
                reset_attempted,
                visible_buttons,
            )
            return BrowserModelSelection(
                requested_label=provider_model_id,
                actual_label=provider_model_id,
                details={
                    "actual_label_source": "picker_unavailable",
                    "driver": "playwright",
                    "model_selection_verified": False,
                    "model_selection_attempted": False,
                    "model_picker_unavailable": True,
                    "home_navigation_attempted": home_navigation_attempted,
                    "fresh_thread_reset_attempted": reset_attempted,
                    "model_verification_wait_attempts": policy.wait_attempts,
                    "model_button_text_before": None,
                    "model_button_text_after": None,
                    "button_debug_snapshot": visible_buttons,
                    "model_menu_snapshot": [],
                },
            )
        model_button_text_before = self._locator_inner_text(model_button)
        logger.info("Selecting Perplexity model '%s' through Playwright", provider_model_id)
        self._screenshot(f"03-model-before-{provider_model_id}")
        if self._body_has_signed_out_marker(page):
            raise PermissionError("Perplexity sign-in overlay blocked model selection.")
        try:
            model_button.click()
        except Exception as exc:
            if self._body_has_signed_out_marker(page):
                raise PermissionError("Perplexity sign-in overlay blocked model selection.") from exc
            raise
        menu_texts = self._model_menu_texts(page)
        self._record_model_menu_snapshot(menu_texts)
        self._screenshot(f"04-model-menu-open-{provider_model_id}")

        option_lookup_source = "menu_scope"
        option = self._find_option_in_menu_scope(page, provider_model_id)
        if option is None:
            option_lookup_source = "role_filter"
            option = self._find_option_via_role_filter(page, provider_model_id)
        if option is None:
            option_lookup_source = "global_fallback"
            option = self._first_visible_locator(
                (
                    page.get_by_role("button", name=provider_model_id),
                    page.get_by_role("option", name=provider_model_id),
                    page.get_by_text(provider_model_id, exact=True),
                )
            )
        if option is None:
            option_lookup_source = "not_found"
            if self._body_has_signed_out_marker(page):
                raise PermissionError("Perplexity sign-in overlay blocked model selection.")
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
                    "actual_label_source": "option_not_found_menu_snapshot",
                    "option_lookup_source": option_lookup_source,
                    "driver": "playwright",
                    "model_selection_verified": False,
                    "model_selection_attempted": False,
                    "home_navigation_attempted": home_navigation_attempted,
                    "model_verification_wait_attempts": policy.wait_attempts,
                    "model_button_text_before": model_button_text_before,
                    "model_button_text_after": model_button_text_before,
                    "button_debug_snapshot": self._button_debug_snapshot(page),
                    "model_menu_snapshot": menu_texts,
                },
            )

        try:
            option.click()
        except Exception as exc:
            if self._body_has_signed_out_marker(page):
                raise PermissionError("Perplexity sign-in overlay blocked model selection.") from exc
            raise
        time.sleep(self._runtime.poll_interval_seconds)
        self._screenshot(f"05-model-after-{provider_model_id}")
        model_button_text_after = self._locator_inner_text(model_button)
        selection_evidence = self._selection_evidence(option)
        model_selection_verified = False
        if policy.verify_button_label:
            model_selection_verified = self._button_text_matches_requested(provider_model_id, model_button_text_after)
        if not model_selection_verified and selection_evidence["verified"]:
            model_selection_verified = True
        if model_selection_verified:
            self._verified_model_labels_at[provider_model_id] = datetime.now(UTC)
        actual_label = provider_model_id
        actual_label_source = "verified_button"
        if not model_selection_verified:
            actual_label = self._infer_active_model_label([model_button_text_after] if model_button_text_after else [])
            if actual_label is not None:
                actual_label_source = "unverified_button_text"
            else:
                actual_label = self._infer_active_model_label(menu_texts)
                if actual_label is not None:
                    actual_label_source = "unverified_menu_snapshot"
                else:
                    actual_label = provider_model_id
                    actual_label_source = "unverified_fallback"
        return BrowserModelSelection(
            requested_label=provider_model_id,
            actual_label=actual_label,
            details={
                "actual_label_source": actual_label_source,
                "option_lookup_source": option_lookup_source,
                "driver": "playwright",
                "model_selection_verified": model_selection_verified,
                "model_selection_attempted": True,
                "home_navigation_attempted": home_navigation_attempted,
                "model_verification_wait_attempts": policy.wait_attempts,
                "model_button_text_before": model_button_text_before,
                "model_button_text_after": model_button_text_after,
                "selection_indicator": selection_evidence["indicator"],
                "selection_indicator_value": selection_evidence["indicator_value"],
                "button_debug_snapshot": self._button_debug_snapshot(page),
                "model_menu_snapshot": menu_texts,
            },
        )

    def enable_thinking(self) -> bool:
        page = self._page_or_raise()
        model_button = self._resolve_model_button(page, attempts=3)
        if model_button is None:
            logger.warning("Cannot enable Thinking: model button not found")
            return False

        button_text = self._locator_inner_text(model_button)
        if button_text and "Thinking" in button_text:
            logger.debug("Thinking already enabled: %s", button_text)
            return True

        model_button.click()
        time.sleep(self._runtime.poll_interval_seconds)

        thinking_el = self._first_visible_locator((
            page.get_by_text("Thinking", exact=True),
        ))
        if thinking_el is None:
            logger.warning("Thinking toggle not found in model menu")
            page.keyboard.press("Escape")
            return False

        thinking_el.click()
        time.sleep(self._runtime.poll_interval_seconds)

        page.keyboard.press("Escape")
        time.sleep(self._runtime.poll_interval_seconds)

        button_text_after = self._locator_inner_text(model_button)
        enabled = button_text_after is not None and "Thinking" in button_text_after
        if enabled:
            logger.info("Thinking mode enabled: %s", button_text_after)
        else:
            logger.warning("Thinking toggle clicked but button shows: %s", button_text_after)
        return enabled

    def attach_files(self, attachments: tuple[FileAttachment, ...]) -> None:
        if not attachments:
            return

        page = self._page_or_raise()
        file_input = page.locator('input[type="file"]')
        try:
            file_input_count = file_input.count()
        except Exception:
            file_input_count = 0

        if file_input_count == 0:
            attach_button = self._first_visible_locator(
                (
                    page.locator(self._selectors.add_files_button),
                    page.locator('[aria-label*="attach" i], [aria-label*="upload" i], [data-testid*="attach" i]'),
                )
            )
            if attach_button is not None:
                attach_button.click()
                time.sleep(self._runtime.poll_interval_seconds)
                file_input = page.locator('input[type="file"]')
                try:
                    file_input_count = file_input.count()
                except Exception:
                    file_input_count = 0
            if file_input_count == 0:
                logger.warning("No file input found on page; skipping %d attachment(s).", len(attachments))
                return

        temp_paths: list[str] = []
        try:
            for attachment in attachments:
                suffix = os.path.splitext(attachment.name)[1] or ".bin"
                with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as handle:
                    handle.write(attachment.data)
                    temp_paths.append(handle.name)

            file_input.set_input_files(temp_paths)
            time.sleep(self._runtime.poll_interval_seconds)
            logger.info("Attached %d file(s) to Perplexity", len(temp_paths))
        finally:
            for path in temp_paths:
                try:
                    os.unlink(path)
                except OSError:
                    pass

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
        self._screenshot("06-prompt-filled")
        self._click_submit(page, policy)
        self._screenshot("07-prompt-submitted")
        try:
            output_text = self._wait_for_response_text(
                page=page,
                prompt=prompt,
                timeout_seconds=timeout_seconds,
            )
        except TimeoutError:
            self._screenshot("08-response-timeout")
            raise
        self._screenshot("09-response-received")
        return BrowserExecutionOutput(
            output_text=output_text["text"],
            details={
                "driver": "playwright",
                "submitted_prompt": prompt,
                "timeout_seconds": timeout_seconds,
                "response_source": output_text["source"],
                "response_candidate_counts": output_text["candidate_counts"],
                "response_candidate_lengths": output_text["candidate_lengths"],
                "response_selected_length": output_text["selected_length"],
                "response_used_body_fallback": output_text["used_body_fallback"],
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
            "verified_model_labels_at": dict(self._verified_model_labels_at),
            "last_model_picker_unavailable_at": self._last_model_picker_unavailable_at,
            "reason": dependency_error,
        }

    def close(self) -> None:
        owner_thread_id = self._session_thread_id
        current_thread_id = threading.get_ident()
        context = self._context
        playwright = self._playwright
        self._clear_runtime_handles()
        if owner_thread_id is not None and owner_thread_id != current_thread_id:
            logger.warning(
                "Skipping direct Playwright shutdown on thread %s; runtime was created on thread %s",
                current_thread_id,
                owner_thread_id,
            )
            return
        if context is not None:
            context.close()
        if playwright is not None:
            playwright.stop()

    def _clear_runtime_handles(self) -> None:
        self._page = None
        self._context = None
        self._playwright = None
        self._playwright_manager = None
        self._session_thread_id = None

    def _screenshot(self, step_name: str) -> str | None:
        """Save a page screenshot to configured dir. Returns saved path, or None if disabled/failed."""
        dest_dir = self._runtime.screenshots_dir
        if not dest_dir or self._page is None:
            return None
        try:
            Path(dest_dir).mkdir(parents=True, exist_ok=True)
            timestamp = datetime.now(UTC).strftime("%Y%m%d-%H%M%S-%f")[:-3]
            safe_step = re.sub(r"[^a-zA-Z0-9_-]+", "_", step_name).strip("_") or "step"
            path = Path(dest_dir) / f"{timestamp}-{safe_step}.png"
            screenshot = getattr(self._page, "screenshot", None)
            if not callable(screenshot):
                return None
            screenshot(path=str(path), full_page=True)
            logger.info("Browser screenshot saved: %s", path)
            return str(path)
        except Exception as exc:
            logger.warning("Browser screenshot '%s' failed: %s", step_name, exc)
            return None

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

    def _find_option_in_menu_scope(self, page: Any, requested: str) -> Any | None:
        for selector in self._selectors.model_menu_candidates:
            try:
                candidate = page.locator(selector).locator(f"text={requested}")
            except Exception:
                continue
            if self._locator_is_visible(candidate):
                return getattr(candidate, "first", candidate)
        return None

    def _find_option_via_role_filter(self, page: Any, requested: str) -> Any | None:
        for raw_selector in self._selectors.model_menu_item_selector.split(","):
            selector = raw_selector.strip()
            if not selector:
                continue
            # Leave broad button matching to the legacy global fallback to avoid off-menu hits.
            if selector == "button":
                continue
            candidate = page.locator(f'{selector}:has-text("{requested}")')
            if self._locator_is_visible(candidate):
                return getattr(candidate, "first", candidate)
        return None

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

    def _extract_catalog_labels(self, menu_texts: list[str]) -> list[str]:
        labels: list[str] = []
        for block in menu_texts:
            for line in block.splitlines():
                normalized = line.strip()
                if not self._looks_like_model_label(normalized):
                    continue
                if normalized not in labels:
                    labels.append(normalized)
        return labels

    def _looks_like_model_label(self, label: str) -> bool:
        if not label or len(label) > 48:
            return False
        normalized = " ".join(label.split())
        blocked = {"thinking", "models", "all models", "reasoning"}
        if normalized.casefold() in blocked:
            return False

        allowed_lowercase = {"mini", "pro", "max", "small", "medium", "large", "preview", "flash"}
        tokens = normalized.split(" ")
        if len(tokens) > 5:
            return False

        for token in tokens:
            cleaned = token.strip("()[],:")
            if not cleaned:
                return False
            if any(char.isdigit() for char in cleaned):
                continue
            if cleaned.casefold() in allowed_lowercase:
                continue
            if cleaned[0].isupper():
                continue
            return False

        return True

    def _wait_for_response_text(self, *, page: Any, prompt: str, timeout_seconds: int) -> dict[str, Any]:
        deadline = time.monotonic() + timeout_seconds
        while time.monotonic() < deadline:
            candidate_texts = self._collect_response_candidates(page=page, prompt=prompt)
            response_text = self._pick_response_text(prompt=prompt, candidate_texts=candidate_texts)
            if response_text is not None and not self._is_response_generating(page):
                logger.info(
                    "Response extracted via source=%s length=%d",
                    response_text["source"],
                    response_text["selected_length"],
                )
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

    def _log_auth_unknown_diagnostics(
        self,
        *,
        page: Any,
        body_text: str,
        prompt_input_visible: bool,
    ) -> None:
        url = ""
        title = ""
        prompt_input_count = -1
        try:
            url = str(getattr(page, "url", "") or "")
        except Exception:
            url = ""
        try:
            title_fn = getattr(page, "title", None)
            if callable(title_fn):
                title = str(title_fn() or "")
        except Exception:
            title = ""
        try:
            locator = page.locator(self._selectors.prompt_input)
            count_fn = getattr(locator, "count", None)
            if callable(count_fn):
                prompt_input_count = int(count_fn())
        except Exception:
            prompt_input_count = -1
        markers_matched = [m for m in self._selectors.signed_out_markers if m in body_text]
        logger.warning(
            "browser_auth_unknown url=%s title=%s body_length=%d "
            "prompt_input_visible=%s prompt_input_count=%d "
            "signed_out_markers_matched=%s body_prefix=%r",
            url,
            title,
            len(body_text),
            prompt_input_visible,
            prompt_input_count,
            markers_matched,
            body_text[:300],
        )

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
        candidate_lengths: dict[str, int] = {}
        for source, candidate in candidate_texts:
            candidate_counts[source] = candidate_counts.get(source, 0) + 1
            cleaned = self._clean_candidate_text(prompt=prompt, candidate=candidate)
            if cleaned:
                cleaned_candidates.append((source, cleaned))
                candidate_lengths[source] = max(candidate_lengths.get(source, 0), len(cleaned))
        if not cleaned_candidates:
            return None
        source, text = max(
            cleaned_candidates,
            key=lambda item: (self._response_source_priority(item[0]), len(item[1])),
        )
        return {
            "text": text,
            "source": source,
            "candidate_counts": candidate_counts,
            "candidate_lengths": candidate_lengths,
            "selected_length": len(text),
            "used_body_fallback": source.startswith("body"),
        }

    def _clean_candidate_text(self, *, prompt: str, candidate: str) -> str | None:
        normalized = candidate.strip()
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

    def _response_source_priority(self, source: str) -> int:
        if source in self._selectors.response_candidates:
            return len(self._selectors.response_candidates) - self._selectors.response_candidates.index(source) + 1
        if source == "body_after_prompt":
            return 1
        return 0

    def _is_response_generating(self, page: Any) -> bool:
        try:
            active = page.evaluate(
                """
                () => {
                  const composer = document.querySelector('[data-ask-input-container="true"]');
                  if (!composer) {
                    return false;
                  }
                  return Array.from(composer.querySelectorAll('button')).some((button) =>
                    (button.getAttribute('aria-label') || '').startsWith('Stop response')
                  );
                }
                """
            )
            if isinstance(active, bool):
                return active
        except Exception:
            pass
        return self._locator_is_visible(page.locator(self._selectors.stop_response_button))

    def _first_visible_locator(self, locators: tuple[Any, ...]) -> Any | None:
        for locator in locators:
            if self._locator_is_visible(locator):
                return getattr(locator, "first", locator)
        return None

    def _resolve_model_button(self, page: Any, *, attempts: int) -> Any | None:
        locators = (
            page.locator(self._selectors.composer_model_button),
            page.locator(self._selectors.model_button),
        )
        for _ in range(max(attempts, 1)):
            button = self._first_visible_locator(locators)
            if button is not None:
                return button
            time.sleep(self._runtime.poll_interval_seconds)
        return None

    def _navigate_home_for_model_selection(self, page: Any) -> bool:
        if not self._base_url:
            return False
        goto = getattr(page, "goto", None)
        if not callable(goto):
            return False
        try:
            logger.info("Navigating Perplexity UI back to %s before model selection.", self._base_url)
            goto(self._base_url, wait_until="domcontentloaded")
            self._wait_for_shell()
        except Exception:
            return False
        return True

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
                () => {
                  const format = (button) => {
                    const ariaLabel = button.getAttribute('aria-label');
                    const text = (button.innerText || '').trim();
                    return ariaLabel ? `${ariaLabel}::${text}` : text;
                  };
                  const composer = document.querySelector('[data-ask-input-container="true"]');
                  const composerButtons = composer
                    ? Array.from(composer.querySelectorAll('button')).map(format).filter(Boolean)
                    : [];
                  if (composerButtons.length) {
                    return composerButtons.slice(0, 16);
                  }
                  return Array.from(document.querySelectorAll('button')).slice(0, 16).map(format).filter(Boolean);
                }
                """
            )
        except Exception:
            return []
        if not isinstance(entries, list):
            return []
        return [str(entry).strip() for entry in entries if str(entry).strip()]

    def _body_text(self, page: Any) -> str:
        try:
            return page.inner_text("body")  # type: ignore[no-any-return]
        except Exception:
            return ""
