from __future__ import annotations

import unittest

from gracekelly.adapters.browser.playwright_driver import PlaywrightBrowserAutomation
from gracekelly.adapters.browser.policy import AuthRecoveryPolicy


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


if __name__ == "__main__":
    unittest.main()
