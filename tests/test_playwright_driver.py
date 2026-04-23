from __future__ import annotations

import os
import threading
import unittest
from collections.abc import Callable
from typing import Any, cast

from gracekelly.adapters.browser.automation import BrowserProfileBusyError
from gracekelly.adapters.browser.playwright_driver import (
    PlaywrightBrowserAutomation,
    PlaywrightBrowserRuntimeConfig,
)
from gracekelly.adapters.browser.policy import AuthRecoveryPolicy, ModelVerificationPolicy
from gracekelly.adapters.browser.session import BrowserSessionConfig, BrowserSessionManager
from gracekelly.core.contracts import FileAttachment


class _FakeLocator:
    def __init__(
        self,
        *,
        visible: bool = False,
        count_value: int | None = None,
        texts: list[str] | None = None,
        inner_text: str | None = None,
        attributes: dict[str, str] | None = None,
        on_click: Callable[[], None] | None = None,
        on_set_input_files: Callable[[list[str]], None] | None = None,
    ) -> None:
        self._visible = visible
        self._count_value = count_value
        self.clicked = False
        self.input_files: list[str] = []
        self._texts = texts or []
        self._inner_text = inner_text
        self._attributes = attributes or {}
        self._on_click = on_click
        self._on_set_input_files = on_set_input_files

    @property
    def first(self) -> _FakeLocator:
        return self

    def is_visible(self) -> bool:
        return self._visible

    def count(self) -> int:
        if self._count_value is not None:
            return self._count_value
        return 1 if self._visible else 0

    def click(self) -> None:
        self.clicked = True
        if self._on_click is not None:
            self._on_click()

    def set_input_files(self, paths: list[str]) -> None:
        self.input_files = list(paths)
        if self._on_set_input_files is not None:
            self._on_set_input_files(paths)

    def all_inner_texts(self) -> list[str]:
        return list(self._texts)

    def inner_text(self) -> str:
        if self._inner_text is None:
            raise RuntimeError("inner_text not configured")
        return self._inner_text

    def get_attribute(self, name: str) -> str | None:
        return self._attributes.get(name)


class _FakePage:
    def __init__(self) -> None:
        self.model_button = _FakeLocator(visible=True, inner_text="Model")
        self.option = _FakeLocator(visible=False)
        self.new_thread_button = _FakeLocator(visible=False, inner_text="New Thread")
        self.stop_response_button = _FakeLocator(visible=False, inner_text="Stop response (Esc)")
        self.file_input = _FakeLocator(visible=False, count_value=0)
        self.add_files_button = _FakeLocator(visible=False, inner_text="Add files or tools")
        self.model_menu = _FakeLocator(
            visible=True,
            texts=["Best\nSelects the best available model\nGPT-5.4\nGemini 3.1 Pro"],
        )
        self.default_timeout_ms: int | None = None
        self.goto_url: str | None = None
        self.keyboard = _FakeKeyboard()

    def locator(self, selector: str) -> _FakeLocator:
        if selector == 'input[type="file"]':
            return self.file_input
        if selector == 'button[aria-label="Add files or tools"]':
            return self.add_files_button
        if "radix-popper" in selector or "role=\"dialog\"" in selector or "role=\"listbox\"" in selector:
            return self.model_menu
        if "Stop response" in selector:
            return self.stop_response_button
        if "New Thread" in selector:
            return self.new_thread_button
        return self.model_button

    def get_by_role(self, role: str, name: str) -> _FakeLocator:
        if name == "Model":
            return self.model_button
        if name == "New Thread":
            return self.new_thread_button
        return self.option

    def get_by_text(self, value: str, exact: bool = False) -> _FakeLocator:
        if value == "Model":
            return self.model_button
        if value == "New Thread":
            return self.new_thread_button
        return self.option

    def set_default_timeout(self, timeout_ms: int) -> None:
        self.default_timeout_ms = timeout_ms

    def goto(self, url: str, wait_until: str) -> None:
        self.goto_url = url

    def evaluate(self, script: str) -> list[str]:
        return [
            "New Thread" if self.new_thread_button.is_visible() else "",
            "Model" if self.model_button.is_visible() else "",
        ]


class _TransientLocator(_FakeLocator):
    def __init__(self, visible_sequence: list[bool], **kwargs: Any) -> None:
        initial_visible = visible_sequence[0] if visible_sequence else False
        super().__init__(visible=initial_visible, **kwargs)
        self._visible_sequence = list(visible_sequence)
        self._checks = 0

    def is_visible(self) -> bool:
        index = min(self._checks, len(self._visible_sequence) - 1)
        self._checks += 1
        return self._visible_sequence[index]

    def count(self) -> int:
        return 1 if self.is_visible() else 0


class _FakeKeyboard:
    def __init__(self) -> None:
        self.pressed: list[str] = []

    def press(self, value: str) -> None:
        self.pressed.append(value)


class _FakeContext:
    def __init__(self) -> None:
        self.closed = False
        self.pages = [_FakePage()]
        self.created_page = _FakePage()
        self.new_page_called = False

    def close(self) -> None:
        self.closed = True

    def new_page(self) -> _FakePage:
        self.new_page_called = True
        return self.created_page


class _FakePlaywright:
    def __init__(self) -> None:
        self.stopped = False

    def stop(self) -> None:
        self.stopped = True


class _LaunchingChromium:
    def __init__(self, context: _FakeContext) -> None:
        self._context = context

    def launch_persistent_context(self, *args: Any, **kwargs: Any) -> _FakeContext:
        return self._context


class _LaunchingPlaywright:
    def __init__(self, context: _FakeContext) -> None:
        self.chromium = _LaunchingChromium(context)
        self.stopped = False

    def stop(self) -> None:
        self.stopped = True


class _LaunchingPlaywrightManager:
    def __init__(self, context: _FakeContext) -> None:
        self.playwright = _LaunchingPlaywright(context)

    def start(self) -> _LaunchingPlaywright:
        return self.playwright


class _CrashingChromium:
    def launch_persistent_context(self, *args: Any, **kwargs: Any) -> _FakeContext:
        raise RuntimeError(
            "BrowserType.launch_persistent_context: Target page, context or browser has been closed\n"
            "Call log:\n"
            "  - [pid=123] <process did exit: exitCode=21, signal=null>"
        )


class _CrashingPlaywright:
    def __init__(self) -> None:
        self.chromium = _CrashingChromium()
        self.stopped = False

    def stop(self) -> None:
        self.stopped = True


class _CrashingPlaywrightManager:
    def __init__(self) -> None:
        self.playwright = _CrashingPlaywright()

    def start(self) -> _CrashingPlaywright:
        return self.playwright


class PlaywrightDriverTests(unittest.TestCase):
    def test_attach_files_uploads_images_via_file_input(self) -> None:
        captured: dict[str, object] = {}

        def _capture_input_files(paths: list[str]) -> None:
            captured["paths"] = list(paths)
            captured["exists_during_upload"] = [os.path.exists(path) for path in paths]
            captured["payloads"] = [open(path, "rb").read() for path in paths]

        driver = PlaywrightBrowserAutomation(
            runtime=PlaywrightBrowserRuntimeConfig(poll_interval_seconds=0),
            sync_playwright_factory=lambda: object(),
        )
        page = _FakePage()
        page.file_input = _FakeLocator(
            visible=False,
            count_value=1,
            on_set_input_files=_capture_input_files,
        )
        driver._page = page
        attachment = FileAttachment(name="photo.png", content_type="image/png", data=b"png-bytes")

        driver.attach_files((attachment,))

        self.assertEqual(captured["exists_during_upload"], [True])
        self.assertEqual(captured["payloads"], [b"png-bytes"])
        self.assertEqual(len(page.file_input.input_files), 1)
        for path in cast(list[str], captured["paths"]):
            self.assertFalse(os.path.exists(path))

    def test_attach_files_logs_warning_when_file_input_is_missing(self) -> None:
        driver = PlaywrightBrowserAutomation(
            runtime=PlaywrightBrowserRuntimeConfig(poll_interval_seconds=0),
            sync_playwright_factory=lambda: object(),
        )
        driver._page = _FakePage()
        attachment = FileAttachment(name="photo.png", content_type="image/png", data=b"png-bytes")

        with self.assertLogs("gracekelly.adapters.browser.playwright_driver", level="WARNING") as captured:
            driver.attach_files((attachment,))

        self.assertEqual(len(captured.output), 1)
        self.assertIn("No file input", captured.output[0])

    def test_infer_auth_status_marks_sign_in_prompt_logged_out(self) -> None:
        driver = PlaywrightBrowserAutomation(sync_playwright_factory=lambda: object())

        status = driver._infer_auth_status(
            body_text="Sign in or create an account\nContinue with Google",
            prompt_input_visible=True,
            policy=AuthRecoveryPolicy(),
        )

        self.assertFalse(status.logged_in)
        assert status.reason is not None
        self.assertIn("Sign-in prompt", status.reason)

    def test_reset_page_state_navigates_home_via_base_url(self) -> None:
        driver = PlaywrightBrowserAutomation(
            runtime=PlaywrightBrowserRuntimeConfig(poll_interval_seconds=0),
            sync_playwright_factory=lambda: object(),
        )
        driver._base_url = "https://www.perplexity.ai/"

        class _FreshThreadPage(_FakePage):
            def __init__(self) -> None:
                super().__init__()
                # prompt_input becomes visible once we're back on home after goto.
                self.model_button = _FakeLocator(visible=True, inner_text="Model", count_value=1)

            def locator(self, selector: str) -> _FakeLocator:
                if selector == 'div#ask-input[role="textbox"][contenteditable="true"]':
                    return self.model_button
                return super().locator(selector)

            def inner_text(self, selector: str) -> str:
                if selector == "body":
                    return "Type @ for connectors and sources"
                return ""

        page = _FreshThreadPage()
        driver._page = page

        result = driver.reset_page_state()

        self.assertTrue(result)
        self.assertEqual(page.goto_url, "https://www.perplexity.ai/")

    def test_reset_page_state_returns_false_without_page(self) -> None:
        driver = PlaywrightBrowserAutomation(sync_playwright_factory=lambda: object())
        self.assertFalse(driver.reset_page_state())

    def test_auth_status_recovers_when_prompt_input_settles_after_wait(self) -> None:
        driver = PlaywrightBrowserAutomation(
            runtime=PlaywrightBrowserRuntimeConfig(poll_interval_seconds=0),
            sync_playwright_factory=lambda: object(),
        )
        transient = _TransientLocator(visible_sequence=[False, True])

        class _TransientPage(_FakePage):
            def __init__(self) -> None:
                super().__init__()
                self.url = "https://www.perplexity.ai/search/abcd1234"

            def locator(self, selector: str) -> _FakeLocator:
                if selector == 'div#ask-input[role="textbox"][contenteditable="true"]':
                    return transient
                return super().locator(selector)

            def inner_text(self, selector: str) -> str:
                if selector == "body":
                    return "Quick answer body text without sign-in markers"
                return ""

            def title(self) -> str:
                return "Perplexity"

        driver._page = _TransientPage()

        status = driver.auth_status(AuthRecoveryPolicy())

        self.assertTrue(status.logged_in)

    def test_auth_status_emits_diagnostic_log_when_logged_out(self) -> None:
        driver = PlaywrightBrowserAutomation(
            runtime=PlaywrightBrowserRuntimeConfig(poll_interval_seconds=0),
            sync_playwright_factory=lambda: object(),
        )

        class _HiddenInputPage(_FakePage):
            def __init__(self) -> None:
                super().__init__()
                self.url = "https://www.perplexity.ai/search/xyz"
                self._hidden = _FakeLocator(visible=False, count_value=1)

            def locator(self, selector: str) -> _FakeLocator:
                if selector == 'div#ask-input[role="textbox"][contenteditable="true"]':
                    return self._hidden
                return super().locator(selector)

            def inner_text(self, selector: str) -> str:
                if selector == "body":
                    return "Loading spinner shell without any markers " * 5
                return ""

            def title(self) -> str:
                return "Perplexity — thread"

        driver._page = _HiddenInputPage()

        with self.assertLogs("gracekelly.adapters.browser.playwright_driver", level="WARNING") as captured:
            status = driver.auth_status(AuthRecoveryPolicy())

        self.assertFalse(status.logged_in)
        self.assertTrue(any("browser_auth_unknown" in record for record in captured.output))
        diagnostic = next(record for record in captured.output if "browser_auth_unknown" in record)
        self.assertIn("url=https://www.perplexity.ai/search/xyz", diagnostic)
        self.assertIn("title=Perplexity", diagnostic)
        self.assertIn("prompt_input_visible=False", diagnostic)
        self.assertIn("prompt_input_count=1", diagnostic)
        self.assertIn("signed_out_markers_matched=[]", diagnostic)

    def test_select_model_raises_permission_error_when_sign_in_overlay_blocks_click(self) -> None:
        driver = PlaywrightBrowserAutomation(
            runtime=PlaywrightBrowserRuntimeConfig(poll_interval_seconds=0),
            sync_playwright_factory=lambda: object(),
        )

        class _SignedOutOverlayPage(_FakePage):
            def __init__(self) -> None:
                super().__init__()
                self.model_button = _FakeLocator(
                    visible=True,
                    inner_text="Model",
                    on_click=lambda: (_ for _ in ()).throw(RuntimeError("click intercepted")),
                )

            def inner_text(self, selector: str) -> str:
                if selector == "body":
                    return "Sign in or create an account\nContinue with Google"
                return ""

        driver._page = _SignedOutOverlayPage()

        with self.assertRaises(PermissionError):
            driver.select_model(
                provider_model_id="GPT-5.4",
                policy=ModelVerificationPolicy(wait_attempts=1),
            )

    def test_pick_response_text_prefers_cleaned_answer_over_shell_noise(self) -> None:
        driver = PlaywrightBrowserAutomation(sync_playwright_factory=lambda: object())

        response_text = driver._pick_response_text(
            prompt="Reply with only OK",
            candidate_texts=[
                ("main div.prose", "Search\nHistory\nReply with only OK\nOK"),
                ("main article", "History"),
                ("body", "Continue with Google"),
            ],
        )

        assert response_text is not None
        self.assertEqual(response_text["text"], "OK")
        self.assertEqual(response_text["source"], "main div.prose")
        self.assertEqual(response_text["candidate_counts"]["main div.prose"], 1)
        self.assertEqual(response_text["candidate_lengths"]["main div.prose"], 2)
        self.assertEqual(response_text["selected_length"], 2)
        self.assertFalse(response_text["used_body_fallback"])

    def test_pick_response_text_prefers_structured_source_over_body_fallback(self) -> None:
        driver = PlaywrightBrowserAutomation(sync_playwright_factory=lambda: object())

        response_text = driver._pick_response_text(
            prompt="Reply with only OK",
            candidate_texts=[
                ("body_after_prompt", "Reply with only OK\nOK\nDiscover\nFinance\nLatest News"),
                ("main article", "Reply with only OK\nOK"),
            ],
        )

        assert response_text is not None
        self.assertEqual(response_text["text"], "OK")
        self.assertEqual(response_text["source"], "main article")
        self.assertFalse(response_text["used_body_fallback"])

    def test_pick_response_text_strips_perplexity_streaming_chrome_lines(self) -> None:
        driver = PlaywrightBrowserAutomation(sync_playwright_factory=lambda: object())

        # Regression for batch-81: response extraction previously returned
        # "Thinking / Ask a follow-up / Model" shell chrome instead of the answer.
        response_text = driver._pick_response_text(
            prompt="Summarise EV adoption",
            candidate_texts=[
                ("body_after_prompt", "Summarise EV adoption\nThinking\nAsk a follow-up\nModel"),
                ("main div.prose", "Summarise EV adoption\nThinking\nEurope leads adoption"),
            ],
        )

        assert response_text is not None
        self.assertEqual(response_text["text"], "Europe leads adoption")
        self.assertEqual(response_text["source"], "main div.prose")

    def test_clean_candidate_text_preserves_line_breaks(self) -> None:
        driver = PlaywrightBrowserAutomation(sync_playwright_factory=lambda: object())

        cleaned = driver._clean_candidate_text(
            prompt="Summarize this",
            candidate="Summarize this\nFirst line\nSecond line",
        )

        self.assertEqual(cleaned, "First line\nSecond line")

    def test_wait_for_response_text_ignores_body_fallback_while_generation_is_active(self) -> None:
        driver = PlaywrightBrowserAutomation(sync_playwright_factory=lambda: object())

        class _GeneratingResponsePage(_FakePage):
            def __init__(self) -> None:
                super().__init__()
                self.stop_response_button = _TransientLocator(
                    [True, True, False],
                    inner_text="Stop response (Esc)",
                )
                self._body_reads = 0

            def inner_text(self, selector: str) -> str:
                if selector != "body":
                    return ""
                payloads = [
                    "Reply with only OK\nDraft",
                    "Reply with only OK\nStill drafting",
                    "Reply with only OK\nOK",
                ]
                index = min(self._body_reads, len(payloads) - 1)
                self._body_reads += 1
                return payloads[index]

        response_text = driver._wait_for_response_text(
            page=_GeneratingResponsePage(),
            prompt="Reply with only OK",
            timeout_seconds=5,
        )

        assert response_text is not None
        self.assertEqual(response_text["text"], "OK")
        self.assertEqual(response_text["source"], "body_after_prompt")

    def test_healthcheck_reports_missing_dependency_when_playwright_unavailable(self) -> None:
        driver = PlaywrightBrowserAutomation()

        health = driver.healthcheck()

        self.assertIn(health["status"], {"ok", "degraded"})
        self.assertEqual(health["driver"], "playwright")

    def test_select_model_reports_menu_label_when_option_is_not_found(self) -> None:
        driver = PlaywrightBrowserAutomation(sync_playwright_factory=lambda: object())
        driver._page = _FakePage()

        selection = driver.select_model(
            provider_model_id="Kimi K2.5",
            policy=ModelVerificationPolicy(),
        )

        self.assertEqual(selection.actual_label, "Best")
        self.assertEqual(selection.details["actual_label_source"], "option_not_found_menu_snapshot")
        self.assertFalse(selection.details["model_selection_attempted"])
        self.assertIn("Best", selection.details["model_menu_snapshot"][0])
        self.assertTrue(driver._page.model_button.clicked)
        self.assertEqual(selection.details["model_button_text_before"], "Model")
        self.assertEqual(selection.details["model_button_text_after"], "Model")
        health = driver.healthcheck()
        observed_model_menu = cast(Any, health["observed_model_menu"])
        self.assertIn("Best", observed_model_menu)
        self.assertIn("GPT-5.4", observed_model_menu)
        self.assertEqual(health["observed_model_menu_source"], "perplexity-model-menu")
        self.assertIsNotNone(health["observed_model_menu_at"])

    def test_select_model_records_post_click_verification_evidence(self) -> None:
        driver = PlaywrightBrowserAutomation(sync_playwright_factory=lambda: object())

        class _SelectablePage(_FakePage):
            def __init__(self) -> None:
                super().__init__()
                self.option = _FakeLocator(
                    visible=True,
                    inner_text="GPT-5.4",
                    attributes={"aria-selected": "true"},
                )
                self.model_button = _FakeLocator(visible=True, inner_text="Current model GPT-5.4")

        driver._page = _SelectablePage()

        selection = driver.select_model(
            provider_model_id="GPT-5.4",
            policy=ModelVerificationPolicy(),
        )

        self.assertTrue(selection.details["model_selection_attempted"])
        self.assertTrue(selection.details["model_selection_verified"])
        self.assertEqual(selection.actual_label, "GPT-5.4")
        self.assertEqual(selection.details["actual_label_source"], "verified_button")
        self.assertEqual(selection.details["model_button_text_after"], "Current model GPT-5.4")
        self.assertEqual(selection.details["selection_indicator"], "aria-selected")
        self.assertEqual(selection.details["selection_indicator_value"], "true")
        health = driver.healthcheck()
        self.assertIn("GPT-5.4", cast(Any, health["verified_model_labels_at"]))

    def test_select_model_verified_path_keeps_requested_actual_label(self) -> None:
        driver = PlaywrightBrowserAutomation(
            runtime=PlaywrightBrowserRuntimeConfig(poll_interval_seconds=0),
            sync_playwright_factory=lambda: object(),
        )

        class _VerifiedSelectionPage(_FakePage):
            def __init__(self) -> None:
                super().__init__()
                self.model_button = _FakeLocator(visible=True, inner_text="Model")
                self.option = _FakeLocator(
                    visible=True,
                    inner_text="GPT-5.4",
                    on_click=self._show_selected_model,
                )

            def _show_selected_model(self) -> None:
                self.model_button._inner_text = "Current model GPT-5.4"

        driver._page = _VerifiedSelectionPage()

        selection = driver.select_model(
            provider_model_id="GPT-5.4",
            policy=ModelVerificationPolicy(),
        )

        self.assertTrue(selection.details["model_selection_verified"])
        self.assertEqual(selection.actual_label, "GPT-5.4")
        self.assertEqual(selection.details["actual_label_source"], "verified_button")

    def test_select_model_unverified_path_reports_button_text_actual_label(self) -> None:
        driver = PlaywrightBrowserAutomation(
            runtime=PlaywrightBrowserRuntimeConfig(poll_interval_seconds=0),
            sync_playwright_factory=lambda: object(),
        )

        class _UnverifiedButtonTextPage(_FakePage):
            def __init__(self) -> None:
                super().__init__()
                self.model_button = _FakeLocator(visible=True, inner_text="Model")
                self.option = _FakeLocator(
                    visible=True,
                    inner_text="Claude Sonnet 4.6",
                    on_click=self._show_unexpected_model,
                )

            def _show_unexpected_model(self) -> None:
                self.model_button._inner_text = "Sonar"

        driver._page = _UnverifiedButtonTextPage()

        selection = driver.select_model(
            provider_model_id="Claude Sonnet 4.6",
            policy=ModelVerificationPolicy(),
        )

        self.assertFalse(selection.details["model_selection_verified"])
        self.assertEqual(selection.actual_label, "Sonar")
        self.assertEqual(selection.details["actual_label_source"], "unverified_button_text")

    def test_select_model_unverified_path_uses_menu_snapshot_when_button_text_is_empty(self) -> None:
        driver = PlaywrightBrowserAutomation(
            runtime=PlaywrightBrowserRuntimeConfig(poll_interval_seconds=0),
            sync_playwright_factory=lambda: object(),
        )

        class _UnverifiedMenuSnapshotPage(_FakePage):
            def __init__(self) -> None:
                super().__init__()
                self.model_button = _FakeLocator(visible=True, inner_text="Model")
                self.model_menu = _FakeLocator(visible=True, texts=["Sonar\nClaude"])
                self.option = _FakeLocator(
                    visible=True,
                    inner_text="Claude Sonnet 4.6",
                    on_click=self._clear_button_text,
                )

            def _clear_button_text(self) -> None:
                self.model_button._inner_text = ""

        driver._page = _UnverifiedMenuSnapshotPage()

        selection = driver.select_model(
            provider_model_id="Claude Sonnet 4.6",
            policy=ModelVerificationPolicy(),
        )

        self.assertFalse(selection.details["model_selection_verified"])
        self.assertEqual(selection.actual_label, "Sonar")
        self.assertEqual(selection.details["actual_label_source"], "unverified_menu_snapshot")

    def test_select_model_unverified_path_falls_back_to_requested_label_without_ui_evidence(self) -> None:
        driver = PlaywrightBrowserAutomation(
            runtime=PlaywrightBrowserRuntimeConfig(poll_interval_seconds=0),
            sync_playwright_factory=lambda: object(),
        )

        class _UnverifiedFallbackPage(_FakePage):
            def __init__(self) -> None:
                super().__init__()
                self.model_button = _FakeLocator(visible=True, inner_text="Model")
                self.model_menu = _FakeLocator(visible=True, texts=["  \n"])
                self.option = _FakeLocator(
                    visible=True,
                    inner_text="Claude Sonnet 4.6",
                    on_click=self._clear_button_text,
                )

            def _clear_button_text(self) -> None:
                self.model_button._inner_text = ""

        driver._page = _UnverifiedFallbackPage()

        selection = driver.select_model(
            provider_model_id="Claude Sonnet 4.6",
            policy=ModelVerificationPolicy(),
        )

        self.assertFalse(selection.details["model_selection_verified"])
        self.assertEqual(selection.actual_label, "Claude Sonnet 4.6")
        self.assertEqual(selection.details["actual_label_source"], "unverified_fallback")

    def test_select_model_waits_for_model_button_visibility(self) -> None:
        driver = PlaywrightBrowserAutomation(sync_playwright_factory=lambda: object())

        class _DelayedButtonPage(_FakePage):
            def __init__(self) -> None:
                super().__init__()
                self.model_button = _TransientLocator(
                    [False, False, True],
                    inner_text="Current model GPT-5.4",
                )
                self.option = _FakeLocator(
                    visible=True,
                    inner_text="GPT-5.4",
                    attributes={"aria-selected": "true"},
                )

        driver._page = _DelayedButtonPage()

        selection = driver.select_model(
            provider_model_id="GPT-5.4",
            policy=ModelVerificationPolicy(wait_attempts=4),
        )

        self.assertTrue(selection.details["model_selection_attempted"])
        self.assertTrue(selection.details["model_selection_verified"])

    def test_select_model_can_resolve_current_model_button_in_composer_shell(self) -> None:
        driver = PlaywrightBrowserAutomation(sync_playwright_factory=lambda: object())

        class _ComposerModelButtonPage(_FakePage):
            def __init__(self) -> None:
                super().__init__()
                self.model_button = _FakeLocator(visible=False, inner_text="Model")
                self.composer_model_button = _FakeLocator(visible=True, inner_text="GPT-5.4")
                self.option = _FakeLocator(
                    visible=True,
                    inner_text="Claude Sonnet 4.6",
                    attributes={"aria-selected": "true"},
                )

            def locator(self, selector: str) -> _FakeLocator:
                if (
                    selector
                    == 'div[data-ask-input-container="true"] button[aria-haspopup="menu"]:not([aria-label="Add files or tools"]):not([aria-label="More"])'
                ):
                    return self.composer_model_button
                return super().locator(selector)

        page = _ComposerModelButtonPage()
        driver._page = page

        selection = driver.select_model(
            provider_model_id="Claude Sonnet 4.6",
            policy=ModelVerificationPolicy(),
        )

        self.assertTrue(selection.details["model_selection_attempted"])
        self.assertTrue(selection.details["model_selection_verified"])
        self.assertEqual(selection.details["model_button_text_before"], "GPT-5.4")
        self.assertTrue(page.composer_model_button.clicked)

    def test_select_model_can_reset_to_new_thread_before_resolving_model_button(self) -> None:
        driver = PlaywrightBrowserAutomation(sync_playwright_factory=lambda: object())

        class _ThreadResetPage(_FakePage):
            def __init__(self) -> None:
                super().__init__()
                self.prompt_input = _FakeLocator(visible=True)
                self.model_button = _FakeLocator(visible=False, inner_text="Model")
                self.option = _FakeLocator(
                    visible=True,
                    inner_text="GPT-5.4",
                    attributes={"aria-selected": "true"},
                )
                self.new_thread_button = _FakeLocator(
                    visible=True,
                    inner_text="New Thread",
                    on_click=self._enable_model_button,
                )

            def _enable_model_button(self) -> None:
                self.model_button = _FakeLocator(visible=True, inner_text="Current model GPT-5.4")
                self.new_thread_button = _FakeLocator(visible=False, inner_text="New Thread")

            def locator(self, selector: str) -> _FakeLocator:
                if selector == 'div#ask-input[role="textbox"][contenteditable="true"]':
                    return self.prompt_input
                return super().locator(selector)

        driver._page = _ThreadResetPage()

        selection = driver.select_model(
            provider_model_id="GPT-5.4",
            policy=ModelVerificationPolicy(wait_attempts=2),
        )

        self.assertTrue(selection.details["model_selection_attempted"])
        self.assertTrue(selection.details["model_selection_verified"])

    def test_select_model_can_navigate_home_before_reset_when_picker_is_missing(self) -> None:
        driver = PlaywrightBrowserAutomation(sync_playwright_factory=lambda: object())

        class _HomeNavigationPage(_FakePage):
            def __init__(self) -> None:
                super().__init__()
                self.prompt_input = _FakeLocator(visible=True)
                self.model_button = _FakeLocator(visible=False, inner_text="Model")
                self.option = _FakeLocator(
                    visible=True,
                    inner_text="GPT-5.4",
                    attributes={"aria-selected": "true"},
                )
                self.new_thread_button = _FakeLocator(visible=False, inner_text="New Thread")

            def goto(self, url: str, wait_until: str) -> None:
                super().goto(url, wait_until)
                self.model_button = _FakeLocator(visible=True, inner_text="Current model GPT-5.4")

            def locator(self, selector: str) -> _FakeLocator:
                if selector == 'div#ask-input[role="textbox"][contenteditable="true"]':
                    return self.prompt_input
                return super().locator(selector)

            def inner_text(self, selector: str) -> str:
                if selector == "body":
                    return "Type @ for connectors and sources\nType / for search modes"
                return ""

        page = _HomeNavigationPage()
        driver._page = page
        driver._base_url = "https://www.perplexity.ai"

        selection = driver.select_model(
            provider_model_id="GPT-5.4",
            policy=ModelVerificationPolicy(wait_attempts=1),
        )

        self.assertTrue(selection.details["model_selection_attempted"])
        self.assertTrue(selection.details["model_selection_verified"])
        self.assertTrue(selection.details["home_navigation_attempted"])
        self.assertEqual(page.goto_url, "https://www.perplexity.ai")

    def test_select_model_degrades_when_picker_stays_unavailable(self) -> None:
        driver = PlaywrightBrowserAutomation(sync_playwright_factory=lambda: object())

        class _UnavailablePickerPage(_FakePage):
            def __init__(self) -> None:
                super().__init__()
                self.prompt_input = _FakeLocator(visible=True)
                self.model_button = _FakeLocator(visible=False, inner_text="Model")
                self.new_thread_button = _FakeLocator(visible=True, inner_text="New Thread")

            def locator(self, selector: str) -> _FakeLocator:
                if selector == 'div#ask-input[role="textbox"][contenteditable="true"]':
                    return self.prompt_input
                return super().locator(selector)

        driver._page = _UnavailablePickerPage()

        selection = driver.select_model(
            provider_model_id="GPT-5.4",
            policy=ModelVerificationPolicy(wait_attempts=2),
        )

        self.assertEqual(selection.actual_label, "GPT-5.4")
        self.assertEqual(selection.details["actual_label_source"], "picker_unavailable")
        self.assertFalse(selection.details["model_selection_verified"])
        self.assertFalse(selection.details["model_selection_attempted"])
        self.assertFalse(selection.details["home_navigation_attempted"])
        self.assertTrue(selection.details["model_picker_unavailable"])
        self.assertIn("New Thread", selection.details["button_debug_snapshot"][0])
        health = driver.healthcheck()
        self.assertIsNotNone(health["last_model_picker_unavailable_at"])

    def test_close_stops_playwright_and_context(self) -> None:
        driver = PlaywrightBrowserAutomation(sync_playwright_factory=lambda: object())
        context = _FakeContext()
        playwright = _FakePlaywright()
        driver._context = context
        driver._playwright = playwright

        driver.close()

        self.assertTrue(context.closed)
        self.assertTrue(playwright.stopped)
        self.assertIsNone(driver._context)
        self.assertIsNone(driver._playwright)

    def test_close_skips_thread_bound_runtime_handles_from_different_thread(self) -> None:
        driver = PlaywrightBrowserAutomation(sync_playwright_factory=lambda: object())
        owner_thread_id = threading.get_ident() + 1

        class _ThreadBoundContext:
            def __init__(self) -> None:
                self.closed = False

            def close(self) -> None:
                if threading.get_ident() != owner_thread_id:
                    raise RuntimeError("cannot switch to a different thread")
                self.closed = True

        class _ThreadBoundPlaywright:
            def __init__(self) -> None:
                self.stopped = False

            def stop(self) -> None:
                if threading.get_ident() != owner_thread_id:
                    raise RuntimeError("cannot switch to a different thread")
                self.stopped = True

        context = _ThreadBoundContext()
        playwright = _ThreadBoundPlaywright()
        driver._context = context
        driver._page = object()
        driver._playwright = playwright
        driver._playwright_manager = object()
        driver._session_thread_id = owner_thread_id

        driver.close()

        self.assertFalse(context.closed)
        self.assertFalse(playwright.stopped)
        self.assertIsNone(driver._context)
        self.assertIsNone(driver._page)
        self.assertIsNone(driver._playwright)
        self.assertIsNone(driver._playwright_manager)
        self.assertIsNone(driver._session_thread_id)

    def test_ensure_session_raises_profile_busy_error_when_profile_is_locked(self) -> None:
        driver = PlaywrightBrowserAutomation(sync_playwright_factory=lambda: _CrashingPlaywrightManager())
        session_manager = BrowserSessionManager(
            BrowserSessionConfig(
                enabled=True,
                provider="perplexity",
                base_url="https://www.perplexity.ai",
                profile_dir=r"D:\GraceKelly\tmp\browser-recon\perplexity-profile",
            )
        )

        with self.assertRaises(BrowserProfileBusyError):
            driver.ensure_session(session_manager)

    def test_ensure_session_opens_a_fresh_page_in_persistent_context(self) -> None:
        context = _FakeContext()
        driver = PlaywrightBrowserAutomation(sync_playwright_factory=lambda: _LaunchingPlaywrightManager(context))
        session_manager = BrowserSessionManager(
            BrowserSessionConfig(
                enabled=True,
                provider="perplexity",
                base_url="https://www.perplexity.ai",
                profile_dir=r"D:\GraceKelly\tmp\browser-recon\perplexity-profile",
            )
        )

        driver.ensure_session(session_manager)

        self.assertTrue(context.new_page_called)
        self.assertIs(driver._page, context.created_page)
        self.assertEqual(driver._base_url, "https://www.perplexity.ai")
        self.assertEqual(context.created_page.goto_url, "https://www.perplexity.ai")


if __name__ == "__main__":
    unittest.main()
