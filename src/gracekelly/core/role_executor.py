from __future__ import annotations

from dataclasses import dataclass, replace
from typing import Callable

from gracekelly.core.contracts import (
    ExecutionAdapter,
    ExecutionRequest,
    ExecutionResult,
)
from gracekelly.core.roles import Role, RoleType, get_role, format_prompt_with_role


@dataclass(frozen=True, slots=True)
class RoleExecutionStep:
    role: Role
    original_prompt: str
    formatted_prompt: str


class RoleExecutor:
    def __init__(self, execute_fn: Callable[[str], str]) -> None:
        self._execute_fn = execute_fn

    def execute_with_role(self, prompt: str, role_type: RoleType) -> str:
        role = get_role(role_type)
        formatted = format_prompt_with_role(role, prompt)
        full_prompt = f"[System] {formatted['system']}\n\n[User] {formatted['user']}"
        return self._execute_fn(full_prompt)

    def verify(self, answer: str, original_prompt: str) -> str:
        prompt = f"Original question: {original_prompt}\n\nAnswer to verify:\n{answer}"
        return self.execute_with_role(prompt, RoleType.VERIFIER)

    def synthesize(self, answers: list[str], original_prompt: str) -> str:
        answers_text = "\n\n---\n\n".join(
            f"Answer {i + 1}:\n{a}" for i, a in enumerate(answers)
        )
        prompt = f"Original question: {original_prompt}\n\nAnswers to synthesize:\n{answers_text}"
        return self.execute_with_role(prompt, RoleType.SYNTHESIZER)

    def judge(self, answer: str, original_prompt: str) -> str:
        prompt = f"Original question: {original_prompt}\n\nAnswer to judge:\n{answer}"
        return self.execute_with_role(prompt, RoleType.JUDGE)

    def challenge(self, answer: str, original_prompt: str) -> str:
        prompt = f"Original question: {original_prompt}\n\nAnswer to challenge:\n{answer}"
        return self.execute_with_role(prompt, RoleType.DEVIL_ADVOCATE)

    def fact_check(self, answer: str, original_prompt: str) -> str:
        prompt = f"Original question: {original_prompt}\n\nAnswer to fact-check:\n{answer}"
        return self.execute_with_role(prompt, RoleType.FACT_VERIFIER)

    def execute_and_verify(self, prompt: str) -> tuple[str, str]:
        answer = self._execute_fn(prompt)
        verification = self.verify(answer, prompt)
        return answer, verification

    def execute_verify_synthesize(self, prompt: str, num_answers: int = 2) -> str:
        answers: list[str] = []
        for _ in range(num_answers):
            answers.append(self._execute_fn(prompt))
        return self.synthesize(answers, prompt)
