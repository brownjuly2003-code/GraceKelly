from __future__ import annotations

import unittest

from gracekelly.adapters.browser.automation import BrowserProfileBusyError
from gracekelly.adapters.browser.playwright_driver import PlaywrightBrowserAutomation
from gracekelly.adapters.browser.session import BrowserSessionConfig, BrowserSessionManager
from gracekelly.adapters.browser.policy import AuthRecoveryPolicy, ModelVerificationPolicy


class _FakeLocator:
    def __init__(
        self,
        *,
        visible: bool = False,
        texts: list[str] | None = None,
        inner_text: str | None = None,
        attributes: dict[str, str] | None = None,
        on_click=None,
    ) -> None:
        self._visible = visible
        self.clicked = False
        self._texts = texts or []
        self._inner_text = inner_text
        self._attributes = attributes or {}
        self._on_click = on_click

    @property
    def first(self) -> "_FakeLocator":
        return self

    def is_visible(self) -> bool:
        return self._visible

    def count(self) -> int:
        return 1 if self._visible else 0

    def click(self) -> None:
        self.clicked = True
        if self._on_click is not None:
            self._on_click()

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
        self.model_menu = _FakeLocator(
            visible=True,
            texts=["Best\nSelects the best available model\nGPT-5.4\nGemini 3.1 Pro"],
        )
        self.default_timeout_ms: int | None = None
        self.goto_url: str | None = None
        self.keyboard = _FakeKeyboard()

    def locator(self, selector: str) -> _FakeLocator:
        if "radix-popper" in selector or "role=\"dialog\"" in selector or "role=\"listbox\"" in selector:
            return self.model_menu
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

    def evaluate(self, script: str):
        return [
            "New Thread" if self.new_thread_button.is_visible() else "",
            "Model" if self.model_button.is_visible() else "",
        ]


class _TransientLocator(_FakeLocator):
    def __init__(self, visible_sequence: list[bool], **kwargs) -> None:
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

    def launch_persistent_context(self, *args, **kwargs) -> _FakeContext:
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
    def launch_persistent_context(self, *args, **kwargs):
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
    def test_infer_auth_status_marks_sign_in_prompt_logged_out(self) -> None:
        driver = PlaywrightBrowserAutomation(sync_playwright_factory=lambda: object())

        status = driver._infer_auth_status(
            body_text="Sign in or create an account\nContinue with Google",
            prompt_input_visible=True,
            policy=AuthRecoveryPolicy(),
        )

        self.assertFalse(status.logged_in)
        self.assertIn("Sign-in prompt", status.reason)

    def test_pick_response_text_prefers_cleaned_answer_over_shell_noise(self) -> None:
        driver = PlaywrightBrowserAutomation(sync_playwright_factory=lambda: object())

        response_text = driver._pick_response_text(
            prompt="Reply with only OK",
            candidate_texts=[
                ("main div.prose", "Search\nModel\nReply with only OK\nOK"),
                ("main article", "Model"),
                ("body", "Continue with Google"),
            ],
        )

        self.assertEqual(response_text["text"], "OK")
        self.assertEqual(response_text["source"], "main div.prose")
        self.assertEqual(response_text["candidate_counts"]["main div.prose"], 1)

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
        self.assertFalse(selection.details["model_selection_attempted"])
        self.assertIn("Best", selection.details["model_menu_snapshot"][0])
        self.assertTrue(driver._page.model_button.clicked)
        self.assertEqual(selection.details["model_button_text_before"], "Model")
        self.assertEqual(selection.details["model_button_text_after"], "Model")
        health = driver.healthcheck()
        self.assertIn("Best", health["observed_model_menu"])
        self.assertIn("GPT-5.4", health["observed_model_menu"])
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
        self.assertEqual(selection.details["model_button_text_after"], "Current model GPT-5.4")
        self.assertEqual(selection.details["selection_indicator"], "aria-selected")
        self.assertEqual(selection.details["selection_indicator_value"], "true")
        health = driver.healthcheck()
        self.assertIn("GPT-5.4", health["verified_model_labels_at"])

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
        self.assertFalse(selection.details["model_selection_verified"])
        self.assertFalse(selection.details["model_selection_attempted"])
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
        self.assertEqual(context.created_page.goto_url, "https://www.perplexity.ai")


if __name__ == "__main__":
    unittest.main()
