from __future__ import annotations

import unittest

from gracekelly.adapters.browser.policy import (
    AuthRecoveryPolicy,
    ModelVerificationPolicy,
    PopupPolicy,
    SubmitPolicy,
)


class PopupPolicyTests(unittest.TestCase):
    def test_defaults(self) -> None:
        policy = PopupPolicy()
        self.assertIn("Cookie Policy", policy.dismissible_titles)
        self.assertEqual(policy.escape_key_retries, 2)

    def test_custom_values(self) -> None:
        policy = PopupPolicy(dismissible_titles=("GDPR",), escape_key_retries=5)
        self.assertEqual(policy.dismissible_titles, ("GDPR",))
        self.assertEqual(policy.escape_key_retries, 5)

    def test_frozen(self) -> None:
        policy = PopupPolicy()
        with self.assertRaises(AttributeError):
            policy.escape_key_retries = 10  # type: ignore[misc]


class AuthRecoveryPolicyTests(unittest.TestCase):
    def test_defaults(self) -> None:
        policy = AuthRecoveryPolicy()
        self.assertFalse(policy.allow_relogin)
        self.assertEqual(policy.max_session_retries, 1)
        self.assertTrue(policy.treat_unknown_login_state_as_logged_out)

    def test_allow_relogin(self) -> None:
        policy = AuthRecoveryPolicy(allow_relogin=True)
        self.assertTrue(policy.allow_relogin)

    def test_treat_unknown_as_logged_in(self) -> None:
        policy = AuthRecoveryPolicy(treat_unknown_login_state_as_logged_out=False)
        self.assertFalse(policy.treat_unknown_login_state_as_logged_out)

    def test_frozen(self) -> None:
        policy = AuthRecoveryPolicy()
        with self.assertRaises(AttributeError):
            policy.allow_relogin = True  # type: ignore[misc]


class ModelVerificationPolicyTests(unittest.TestCase):
    def test_defaults(self) -> None:
        policy = ModelVerificationPolicy()
        self.assertTrue(policy.allow_alias_match)
        self.assertEqual(policy.wait_attempts, 5)
        self.assertTrue(policy.verify_button_label)

    def test_strict_no_alias(self) -> None:
        policy = ModelVerificationPolicy(allow_alias_match=False)
        self.assertFalse(policy.allow_alias_match)

    def test_frozen(self) -> None:
        policy = ModelVerificationPolicy()
        with self.assertRaises(AttributeError):
            policy.wait_attempts = 99  # type: ignore[misc]


class SubmitPolicyTests(unittest.TestCase):
    def test_defaults(self) -> None:
        policy = SubmitPolicy()
        self.assertEqual(policy.click_attempts, 3)
        self.assertTrue(policy.allow_js_fallback)
        self.assertIsInstance(policy.blocked_overlay_markers, tuple)
        self.assertTrue(len(policy.blocked_overlay_markers) > 0)

    def test_custom_click_attempts(self) -> None:
        policy = SubmitPolicy(click_attempts=1, allow_js_fallback=False)
        self.assertEqual(policy.click_attempts, 1)
        self.assertFalse(policy.allow_js_fallback)

    def test_frozen(self) -> None:
        policy = SubmitPolicy()
        with self.assertRaises(AttributeError):
            policy.click_attempts = 10  # type: ignore[misc]
