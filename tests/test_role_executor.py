from __future__ import annotations

import unittest
from dataclasses import FrozenInstanceError
from unittest.mock import Mock

from gracekelly.core.role_executor import RoleExecutionStep, RoleExecutor
from gracekelly.core.roles import RoleType, get_role


class RoleExecutorTests(unittest.TestCase):
    def test_execute_with_role_calls_fn(self) -> None:
        execute_fn = Mock(return_value="ok")
        executor = RoleExecutor(execute_fn)

        executor.execute_with_role("prompt", RoleType.VERIFIER)

        execute_fn.assert_called_once()

    def test_execute_with_role_includes_system_prompt(self) -> None:
        execute_fn = Mock(return_value="ok")
        executor = RoleExecutor(execute_fn)

        executor.execute_with_role("prompt", RoleType.VERIFIER)

        self.assertIn("verification specialist", execute_fn.call_args.args[0])

    def test_execute_with_role_includes_user_prompt(self) -> None:
        execute_fn = Mock(return_value="ok")
        executor = RoleExecutor(execute_fn)

        executor.execute_with_role("prompt", RoleType.VERIFIER)

        self.assertIn("prompt", execute_fn.call_args.args[0])

    def test_verify_includes_answer(self) -> None:
        execute_fn = Mock(return_value="ok")
        executor = RoleExecutor(execute_fn)

        executor.verify("my answer", "question")

        self.assertIn("my answer", execute_fn.call_args.args[0])

    def test_synthesize_includes_all_answers(self) -> None:
        execute_fn = Mock(return_value="ok")
        executor = RoleExecutor(execute_fn)

        executor.synthesize(["a1", "a2"], "q")

        self.assertIn("Answer 1", execute_fn.call_args.args[0])
        self.assertIn("Answer 2", execute_fn.call_args.args[0])

    def test_judge_uses_judge_role(self) -> None:
        execute_fn = Mock(return_value="ok")
        executor = RoleExecutor(execute_fn)

        executor.judge("answer", "question")

        self.assertIn("impartial quality judge", execute_fn.call_args.args[0])

    def test_challenge_uses_devil_advocate(self) -> None:
        execute_fn = Mock(return_value="ok")
        executor = RoleExecutor(execute_fn)

        executor.challenge("answer", "question")

        self.assertIn("devil's advocate", execute_fn.call_args.args[0])

    def test_fact_check_uses_fact_verifier(self) -> None:
        execute_fn = Mock(return_value="ok")
        executor = RoleExecutor(execute_fn)

        executor.fact_check("answer", "question")

        self.assertIn("fact-checking specialist", execute_fn.call_args.args[0])

    def test_execute_and_verify_returns_tuple(self) -> None:
        execute_fn = Mock(side_effect=["answer", "verification"])
        executor = RoleExecutor(execute_fn)

        result = executor.execute_and_verify("prompt")

        self.assertEqual(("answer", "verification"), result)

    def test_execute_and_verify_calls_fn_twice(self) -> None:
        execute_fn = Mock(side_effect=["answer", "verification"])
        executor = RoleExecutor(execute_fn)

        executor.execute_and_verify("prompt")

        self.assertEqual(2, execute_fn.call_count)

    def test_execute_verify_synthesize_default_two(self) -> None:
        execute_fn = Mock(side_effect=["answer1", "answer2", "synthesis"])
        executor = RoleExecutor(execute_fn)

        executor.execute_verify_synthesize("prompt")

        self.assertEqual(3, execute_fn.call_count)

    def test_execute_verify_synthesize_custom_count(self) -> None:
        execute_fn = Mock(side_effect=["answer1", "answer2", "answer3", "synthesis"])
        executor = RoleExecutor(execute_fn)

        executor.execute_verify_synthesize("prompt", num_answers=3)

        self.assertEqual(4, execute_fn.call_count)

    def test_role_execution_step_frozen(self) -> None:
        step = RoleExecutionStep(
            role=get_role(RoleType.VERIFIER),
            original_prompt="original",
            formatted_prompt="formatted",
        )

        with self.assertRaises(FrozenInstanceError):
            setattr(step, "original_prompt", "changed")

    def test_all_role_methods_exist(self) -> None:
        executor = RoleExecutor(lambda prompt: prompt)

        self.assertTrue(hasattr(executor, "verify"))
        self.assertTrue(hasattr(executor, "synthesize"))
        self.assertTrue(hasattr(executor, "judge"))
        self.assertTrue(hasattr(executor, "challenge"))
        self.assertTrue(hasattr(executor, "fact_check"))


if __name__ == "__main__":
    unittest.main()
