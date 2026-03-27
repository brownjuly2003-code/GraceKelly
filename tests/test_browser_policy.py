from __future__ import annotations

import unittest

from gracekelly.adapters.browser.policy import (
    AuthRecoveryPolicy,
    ModelVerificationPolicy,
    PopupPolicy,
    SubmitPolicy,
)


class PopupPolicyTests(unittest.TestCase):
    def test_default_dismissible_titles(self) -> None:
        policy = PopupPolicy()
        self.assertIn("Cookie Policy", policy.dismissible_titles)
        self.assertIn("Sign in", policy.dismissible_titles)
        self.assertIn("Upgrade", policy.dismissible_titles)

    def test_default_escape_key_retries(self) -> None:
        self.assertEqual(PopupPolicy().escape_key_retries, 2)

    def test_custom_dismissible_titles(self) -> None:
        policy = PopupPolicy(dismissible_titles=("Banner",))
        self.assertEqual(policy.dismissible_titles, ("Banner",))

    def test_custom_escape_key_retries(self) -> None:
        policy = PopupPolicy(escape_key_retries=5)
        self.assertEqual(policy.escape_key_retries, 5)

    def test_is_frozen(self) -> None:
        policy = PopupPolicy()
        with self.assertRaises(AttributeError):
            policy.escape_key_retries = 99  # type: ignore[misc]

    def test_equality(self) -> None:
        self.assertEqual(PopupPolicy(), PopupPolicy())
        self.assertNotEqual(PopupPolicy(), PopupPolicy(escape_key_retries=5))


class AuthRecoveryPolicyTests(unittest.TestCase):
    def test_default_allow_relogin_false(self) -> None:
        self.assertFalse(AuthRecoveryPolicy().allow_relogin)

    def test_default_max_session_retries(self) -> None:
        self.assertEqual(AuthRecoveryPolicy().max_session_retries, 1)

    def test_default_treat_unknown_as_logged_out(self) -> None:
        self.assertTrue(AuthRecoveryPolicy().treat_unknown_login_state_as_logged_out)

    def test_custom_allow_relogin(self) -> None:
        policy = AuthRecoveryPolicy(allow_relogin=True)
        self.assertTrue(policy.allow_relogin)

    def test_custom_max_retries(self) -> None:
        policy = AuthRecoveryPolicy(max_session_retries=3)
        self.assertEqual(policy.max_session_retries, 3)

    def test_is_frozen(self) -> None:
        policy = AuthRecoveryPolicy()
        with self.assertRaises(AttributeError):
            policy.allow_relogin = True  # type: ignore[misc]


class ModelVerificationPolicyTests(unittest.TestCase):
    def test_default_allow_alias_match_true(self) -> None:
        self.assertTrue(ModelVerificationPolicy().allow_alias_match)

    def test_default_wait_attempts(self) -> None:
        self.assertEqual(ModelVerificationPolicy().wait_attempts, 5)

    def test_default_verify_button_label_true(self) -> None:
        self.assertTrue(ModelVerificationPolicy().verify_button_label)

    def test_custom_wait_attempts(self) -> None:
        policy = ModelVerificationPolicy(wait_attempts=10)
        self.assertEqual(policy.wait_attempts, 10)

    def test_custom_allow_alias_match_false(self) -> None:
        policy = ModelVerificationPolicy(allow_alias_match=False)
        self.assertFalse(policy.allow_alias_match)

    def test_is_frozen(self) -> None:
        policy = ModelVerificationPolicy()
        with self.assertRaises(AttributeError):
            policy.wait_attempts = 99  # type: ignore[misc]


class SubmitPolicyTests(unittest.TestCase):
    def test_default_click_attempts(self) -> None:
        self.assertEqual(SubmitPolicy().click_attempts, 3)

    def test_default_allow_js_fallback_true(self) -> None:
        self.assertTrue(SubmitPolicy().allow_js_fallback)

    def test_default_blocked_overlay_markers_non_empty(self) -> None:
        markers = SubmitPolicy().blocked_overlay_markers
        self.assertGreater(len(markers), 0)

    def test_default_blocked_overlay_contains_animate_in(self) -> None:
        self.assertIn("animate-in", SubmitPolicy().blocked_overlay_markers)

    def test_custom_click_attempts(self) -> None:
        policy = SubmitPolicy(click_attempts=5)
        self.assertEqual(policy.click_attempts, 5)

    def test_custom_blocked_overlay_markers(self) -> None:
        policy = SubmitPolicy(blocked_overlay_markers=("my-marker",))
        self.assertEqual(policy.blocked_overlay_markers, ("my-marker",))

    def test_is_frozen(self) -> None:
        policy = SubmitPolicy()
        with self.assertRaises(AttributeError):
            policy.click_attempts = 99  # type: ignore[misc]

    def test_equality(self) -> None:
        self.assertEqual(SubmitPolicy(), SubmitPolicy())
        self.assertNotEqual(SubmitPolicy(), SubmitPolicy(click_attempts=1))


if __name__ == "__main__":
    unittest.main()
