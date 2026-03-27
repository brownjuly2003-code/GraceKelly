from __future__ import annotations

import unittest

from gracekelly.adapters.browser.selectors import PerplexitySelectors


class PerplexitySelectorsDefaultsTests(unittest.TestCase):
    def setUp(self) -> None:
        self.sel = PerplexitySelectors()

    def test_prompt_input_is_string(self) -> None:
        self.assertIsInstance(self.sel.prompt_input, str)
        self.assertTrue(self.sel.prompt_input)

    def test_model_button_is_string(self) -> None:
        self.assertIsInstance(self.sel.model_button, str)
        self.assertTrue(self.sel.model_button)

    def test_submit_button_is_string(self) -> None:
        self.assertIsInstance(self.sel.submit_button, str)
        self.assertTrue(self.sel.submit_button)

    def test_stop_response_button_is_string(self) -> None:
        self.assertIsInstance(self.sel.stop_response_button, str)
        self.assertTrue(self.sel.stop_response_button)

    def test_response_candidates_is_non_empty_tuple(self) -> None:
        self.assertIsInstance(self.sel.response_candidates, tuple)
        self.assertGreater(len(self.sel.response_candidates), 0)

    def test_model_menu_candidates_is_non_empty_tuple(self) -> None:
        self.assertIsInstance(self.sel.model_menu_candidates, tuple)
        self.assertGreater(len(self.sel.model_menu_candidates), 0)

    def test_ready_markers_is_non_empty_tuple(self) -> None:
        self.assertIsInstance(self.sel.ready_markers, tuple)
        self.assertGreater(len(self.sel.ready_markers), 0)

    def test_signed_out_markers_contains_sign_in_text(self) -> None:
        self.assertTrue(
            any("Sign in" in marker for marker in self.sel.signed_out_markers)
        )

    def test_shell_noise_lines_is_non_empty_tuple(self) -> None:
        self.assertIsInstance(self.sel.shell_noise_lines, tuple)
        self.assertGreater(len(self.sel.shell_noise_lines), 0)

    def test_shell_noise_contains_search(self) -> None:
        self.assertIn("Search", self.sel.shell_noise_lines)

    def test_cookie_button_names_non_empty(self) -> None:
        self.assertGreater(len(self.sel.cookie_button_names), 0)
        self.assertIn("Accept All Cookies", self.sel.cookie_button_names)

    def test_new_thread_button_names_non_empty(self) -> None:
        self.assertGreater(len(self.sel.new_thread_button_names), 0)
        self.assertIn("New Thread", self.sel.new_thread_button_names)

    def test_is_frozen(self) -> None:
        with self.assertRaises(AttributeError):
            self.sel.submit_button = "other"  # type: ignore[misc]

    def test_equality_with_same_defaults(self) -> None:
        self.assertEqual(PerplexitySelectors(), PerplexitySelectors())


class PerplexitySelectorsCustomTests(unittest.TestCase):
    def test_custom_prompt_input(self) -> None:
        sel = PerplexitySelectors(prompt_input="#my-input")
        self.assertEqual(sel.prompt_input, "#my-input")

    def test_custom_response_candidates(self) -> None:
        sel = PerplexitySelectors(response_candidates=("main .answer",))
        self.assertEqual(sel.response_candidates, ("main .answer",))

    def test_custom_ready_markers(self) -> None:
        sel = PerplexitySelectors(ready_markers=("Ready",))
        self.assertEqual(sel.ready_markers, ("Ready",))

    def test_custom_differs_from_default(self) -> None:
        custom = PerplexitySelectors(submit_button="#submit")
        default = PerplexitySelectors()
        self.assertNotEqual(custom, default)


if __name__ == "__main__":
    unittest.main()
