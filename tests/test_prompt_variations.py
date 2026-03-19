from __future__ import annotations

import unittest

from gracekelly.core.prompt_variations import generate_variations


class PromptVariationsTests(unittest.TestCase):
    def test_default_count_is_three(self) -> None:
        self.assertEqual(len(generate_variations("test")), 3)

    def test_first_variation_is_original(self) -> None:
        self.assertEqual(generate_variations("hello")[0], "hello")

    def test_three_variations_are_unique(self) -> None:
        self.assertEqual(len(set(generate_variations("test", 3))), 3)

    def test_nine_variations_all_unique(self) -> None:
        self.assertEqual(len(set(generate_variations("test", 9))), 9)

    def test_count_one_returns_original(self) -> None:
        self.assertEqual(generate_variations("hello", 1), ["hello"])

    def test_count_twelve_cycles_templates(self) -> None:
        result = generate_variations("x", 12)
        self.assertEqual(len(result), 12)
        self.assertEqual(result[0], result[9])

    def test_empty_prompt_raises_value_error(self) -> None:
        with self.assertRaises(ValueError):
            generate_variations("")

    def test_whitespace_prompt_raises_value_error(self) -> None:
        with self.assertRaises(ValueError):
            generate_variations("   ")

    def test_all_variations_contain_prompt_text(self) -> None:
        self.assertTrue(all("quantum" in item for item in generate_variations("quantum", 9)))

    def test_second_variation_starts_with_explain(self) -> None:
        self.assertTrue(generate_variations("test", 2)[1].startswith("Explain step by step:"))


if __name__ == "__main__":
    unittest.main()
