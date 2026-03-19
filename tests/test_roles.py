from __future__ import annotations

import unittest
from dataclasses import FrozenInstanceError

from gracekelly.core.models import MODEL_SPECS
from gracekelly.core.roles import (
    ROLES,
    RoleType,
    format_prompt_with_role,
    get_role,
)


class RoleTests(unittest.TestCase):
    def test_all_role_types_have_definitions(self) -> None:
        for role_type in RoleType:
            self.assertIn(role_type, ROLES)

    def test_role_count_matches_enum(self) -> None:
        self.assertEqual(len(ROLES), len(RoleType))

    def test_all_system_prompts_are_nonempty(self) -> None:
        for role in ROLES.values():
            self.assertGreater(len(role.system_prompt), 20)

    def test_all_preferred_models_are_valid(self) -> None:
        valid_model_ids = {spec.id for spec in MODEL_SPECS}
        for role in ROLES.values():
            for model_id in role.preferred_models:
                self.assertIn(model_id, valid_model_ids)

    def test_all_roles_require_reasoning(self) -> None:
        for role in ROLES.values():
            self.assertTrue(role.reasoning_required)

    def test_get_role_returns_correct_type(self) -> None:
        role = get_role(RoleType.JUDGE)
        self.assertEqual(role.role_type, RoleType.JUDGE)

    def test_get_role_raises_on_invalid(self) -> None:
        with self.assertRaises(KeyError):
            get_role("nonexistent")  # type: ignore[arg-type]

    def test_format_prompt_structure(self) -> None:
        role = get_role(RoleType.VERIFIER)
        prompt = format_prompt_with_role(role, "Check this answer")
        self.assertEqual(set(prompt.keys()), {"system", "user"})

    def test_format_prompt_preserves_user_prompt(self) -> None:
        role = get_role(RoleType.VERIFIER)
        prompt = format_prompt_with_role(role, "Original prompt")
        self.assertEqual(prompt["user"], "Original prompt")

    def test_format_prompt_uses_role_system_prompt(self) -> None:
        role = get_role(RoleType.VERIFIER)
        prompt = format_prompt_with_role(role, "Original prompt")
        self.assertEqual(prompt["system"], role.system_prompt)

    def test_roles_are_frozen(self) -> None:
        role = get_role(RoleType.VERIFIER)
        with self.assertRaises(FrozenInstanceError):
            role.system_prompt = "x"  # type: ignore[misc]

    def test_verifier_system_prompt_contains_accuracy(self) -> None:
        prompt = get_role(RoleType.VERIFIER).system_prompt.lower()
        self.assertIn("accuracy", prompt)

    def test_devil_advocate_system_prompt_contains_challenge(self) -> None:
        prompt = get_role(RoleType.DEVIL_ADVOCATE).system_prompt.lower()
        self.assertTrue("challenge" in prompt or "weakness" in prompt)

    def test_decomposer_system_prompt_contains_break_down(self) -> None:
        prompt = get_role(RoleType.DECOMPOSER).system_prompt.lower()
        self.assertTrue("break down" in prompt or "sub-question" in prompt)

    def test_role_type_is_str_enum(self) -> None:
        self.assertEqual(RoleType.VERIFIER, "verifier")


if __name__ == "__main__":
    unittest.main()
