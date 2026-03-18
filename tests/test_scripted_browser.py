from __future__ import annotations

import unittest

from gracekelly.adapters.browser.automation import NullBrowserAutomation
from gracekelly.adapters.browser.policy import (
    AuthRecoveryPolicy,
    ModelVerificationPolicy,
    PopupPolicy,
    SubmitPolicy,
)
from gracekelly.adapters.browser.scripted import (
    ScriptedBrowserAutomation,
    ScriptedBrowserScenario,
)
from gracekelly.adapters.browser.session import BrowserSessionConfig, BrowserSessionManager


def _configured_session() -> BrowserSessionManager:
    return BrowserSessionManager(
        BrowserSessionConfig(
            enabled=True,
            provider="perplexity",
            base_url="https://www.perplexity.ai",
            profile_dir="/tmp/test",
        )
    )


def _unconfigured_session() -> BrowserSessionManager:
    return BrowserSessionManager(
        BrowserSessionConfig(
            enabled=False,
            provider="perplexity",
            base_url="https://www.perplexity.ai",
        )
    )


class ScriptedBrowserAutomationTests(unittest.TestCase):
    def test_ensure_session_configured(self) -> None:
        automation = ScriptedBrowserAutomation()
        automation.ensure_session(_configured_session())

    def test_ensure_session_unconfigured_raises(self) -> None:
        automation = ScriptedBrowserAutomation()
        with self.assertRaises(NotImplementedError):
            automation.ensure_session(_unconfigured_session())

    def test_dismiss_popups_noop(self) -> None:
        automation = ScriptedBrowserAutomation()
        result = automation.dismiss_popups(PopupPolicy())
        self.assertIsNone(result)

    def test_auth_status_logged_in(self) -> None:
        automation = ScriptedBrowserAutomation(ScriptedBrowserScenario(logged_in=True))
        status = automation.auth_status(AuthRecoveryPolicy())
        self.assertTrue(status.logged_in)
        self.assertIsNone(status.reason)

    def test_auth_status_logged_out(self) -> None:
        automation = ScriptedBrowserAutomation(ScriptedBrowserScenario(logged_in=False))
        status = automation.auth_status(AuthRecoveryPolicy())
        self.assertFalse(status.logged_in)
        self.assertIn("logged out", status.reason)

    def test_recover_auth_delegates_to_auth_status(self) -> None:
        automation = ScriptedBrowserAutomation(ScriptedBrowserScenario(logged_in=False))
        status = automation.recover_auth(AuthRecoveryPolicy())
        self.assertFalse(status.logged_in)

    def test_select_model_default(self) -> None:
        automation = ScriptedBrowserAutomation()
        selection = automation.select_model(
            provider_model_id="GPT-5.4",
            policy=ModelVerificationPolicy(),
        )
        self.assertEqual(selection.requested_label, "GPT-5.4")
        self.assertEqual(selection.actual_label, "GPT-5.4")
        self.assertEqual(selection.details["driver"], "scripted")

    def test_select_model_with_custom_label(self) -> None:
        automation = ScriptedBrowserAutomation(
            ScriptedBrowserScenario(actual_model_label="Claude Sonnet 4.6")
        )
        selection = automation.select_model(
            provider_model_id="GPT-5.4",
            policy=ModelVerificationPolicy(),
        )
        self.assertEqual(selection.requested_label, "GPT-5.4")
        self.assertEqual(selection.actual_label, "Claude Sonnet 4.6")

    def test_submit_prompt(self) -> None:
        automation = ScriptedBrowserAutomation(
            ScriptedBrowserScenario(output_text="Hello!")
        )
        output = automation.submit_prompt(
            prompt="Say hello",
            policy=SubmitPolicy(),
            timeout_seconds=30,
        )
        self.assertEqual(output.output_text, "Hello!")
        self.assertEqual(output.details["submitted_prompt"], "Say hello")
        self.assertEqual(output.details["timeout_seconds"], 30)

    def test_healthcheck(self) -> None:
        automation = ScriptedBrowserAutomation()
        health = automation.healthcheck()
        self.assertEqual(health["status"], "ok")
        self.assertTrue(health["implemented"])
        self.assertEqual(health["driver"], "scripted")
        self.assertTrue(health["logged_in"])

    def test_default_scenario(self) -> None:
        automation = ScriptedBrowserAutomation()
        output = automation.submit_prompt(prompt="test", policy=SubmitPolicy(), timeout_seconds=10)
        self.assertEqual(output.output_text, "scripted browser result")


class NullBrowserAutomationTests(unittest.TestCase):
    def test_ensure_session_raises(self) -> None:
        with self.assertRaises(NotImplementedError):
            NullBrowserAutomation().ensure_session(_configured_session())

    def test_dismiss_popups_raises(self) -> None:
        with self.assertRaises(NotImplementedError):
            NullBrowserAutomation().dismiss_popups(PopupPolicy())

    def test_auth_status_raises(self) -> None:
        with self.assertRaises(NotImplementedError):
            NullBrowserAutomation().auth_status(AuthRecoveryPolicy())

    def test_recover_auth_raises(self) -> None:
        with self.assertRaises(NotImplementedError):
            NullBrowserAutomation().recover_auth(AuthRecoveryPolicy())

    def test_select_model_raises(self) -> None:
        with self.assertRaises(NotImplementedError):
            NullBrowserAutomation().select_model(
                provider_model_id="test",
                policy=ModelVerificationPolicy(),
            )

    def test_submit_prompt_raises(self) -> None:
        with self.assertRaises(NotImplementedError):
            NullBrowserAutomation().submit_prompt(
                prompt="test",
                policy=SubmitPolicy(),
                timeout_seconds=10,
            )

    def test_healthcheck_degraded(self) -> None:
        health = NullBrowserAutomation().healthcheck()
        self.assertEqual(health["status"], "degraded")
        self.assertFalse(health["implemented"])
