from __future__ import annotations

import unittest

from gracekelly.adapters.browser.automation import BrowserProfileBusyError
from gracekelly.adapters.browser.playwright_driver import PlaywrightBrowserAutomation
from gracekelly.adapters.browser.session import BrowserSessionConfig, BrowserSessionManager
from gracekelly.adapters.browser.policy import AuthRecoveryPolicy, ModelVerificationPolicy


class _FakeLocator:
    def __init__(self, *, visible: bool = False, texts: list[str] | None = None) -> None:
        self._visible = visible
        self.clicked = False
        self._texts = texts or []

    @property
    def first(self) -> "_FakeLocator":
        return self

    def is_visible(self) -> bool:
        return self._visible

    def count(self) -> int:
        return 1 if self._visible else 0

    def click(self) -> None:
        self.clicked = True

    def all_inner_texts(self) -> list[str]:
        return list(self._texts)


class _FakePage:
    def __init__(self) -> None:
        self.model_button = _FakeLocator(visible=True)
        self.option = _FakeLocator(visible=False)
        self.model_menu = _FakeLocator(
            visible=True,
            texts=["Best\nSelects the best available model\nGPT-5.4\nGemini 3.1 Pro"],
        )

    def locator(self, selector: str) -> _FakeLocator:
        if "radix-popper" in selector or "role=\"dialog\"" in selector or "role=\"listbox\"" in selector:
            return self.model_menu
        return self.model_button

    def get_by_role(self, role: str, name: str) -> _FakeLocator:
        return self.option

    def get_by_text(self, value: str, exact: bool = False) -> _FakeLocator:
        return self.option


class _FakeContext:
    def __init__(self) -> None:
        self.closed = False

    def close(self) -> None:
        self.closed = True


class _FakePlaywright:
    def __init__(self) -> None:
        self.stopped = False

    def stop(self) -> None:
        self.stopped = True


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
                "Search\nModel\nReply with only OK\nOK",
                "Model",
                "Continue with Google",
            ],
        )

        self.assertEqual(response_text, "OK")

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
        health = driver.healthcheck()
        self.assertIn("Best", health["observed_model_menu"])
        self.assertIn("GPT-5.4", health["observed_model_menu"])
        self.assertEqual(health["observed_model_menu_source"], "perplexity-model-menu")
        self.assertIsNotNone(health["observed_model_menu_at"])

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


if __name__ == "__main__":
    unittest.main()
