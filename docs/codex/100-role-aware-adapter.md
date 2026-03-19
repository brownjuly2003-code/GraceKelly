# 100: Role-Aware Adapter Wrapper — TODO

Phase 7 (Role System). Dependency: roles.py exists.
Complexity: moderate | Runs: 2

```
## GOAL
Create a role-aware adapter wrapper that injects system prompts from roles into execution requests. Two new files: `src/gracekelly/core/role_executor.py` and `tests/test_role_executor.py`.

## CONTEXT
Files to CREATE:
- `src/gracekelly/core/role_executor.py` — wrapper that adds role system prompts
- `tests/test_role_executor.py` — unit tests with mock adapter

Files to READ (do NOT modify):
- `src/gracekelly/core/roles.py` — RoleType, Role, get_role(), format_prompt_with_role()
- `src/gracekelly/core/contracts.py` — ExecutionAdapter, ExecutionRequest, ExecutionResult, StepStatus

Architecture:
- Python >=3.11, no external dependencies
- RoleExecutor wraps an ExecutionAdapter and modifies the prompt before calling it
- Tests mock the inner adapter
- Test runner: `python -m pytest tests/test_role_executor.py -q`

## CONSTRAINTS
- Create ONLY the two files listed above. Do NOT modify any existing files.
- Follow these instructions EXACTLY.
- Do NOT add: logging, comments, docstrings.
- Preserve project code style: 4-space indentation, snake_case, `from __future__ import annotations`.

### role_executor.py specification

```python
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
```

That is the COMPLETE implementation. Copy it exactly.

### test_role_executor.py specification

Exactly these tests:

1. `test_execute_with_role_calls_fn` — execute_with_role("prompt", VERIFIER) calls execute_fn once
2. `test_execute_with_role_includes_system_prompt` — the prompt passed to fn contains "verification specialist"
3. `test_execute_with_role_includes_user_prompt` — the prompt passed to fn contains original user prompt
4. `test_verify_includes_answer` — verify("my answer", "question") → fn receives "my answer"
5. `test_synthesize_includes_all_answers` — synthesize(["a1", "a2"], "q") → fn receives both "Answer 1" and "Answer 2"
6. `test_judge_uses_judge_role` — judge() → fn receives "impartial quality judge"
7. `test_challenge_uses_devil_advocate` — challenge() → fn receives "devil's advocate"
8. `test_fact_check_uses_fact_verifier` — fact_check() → fn receives "fact-checking specialist"
9. `test_execute_and_verify_returns_tuple` — returns tuple of (answer, verification)
10. `test_execute_and_verify_calls_fn_twice` — fn called exactly 2 times
11. `test_execute_verify_synthesize_default_two` — fn called 3 times (2 answers + 1 synthesis)
12. `test_execute_verify_synthesize_custom_count` — num_answers=3 → fn called 4 times
13. `test_role_execution_step_frozen` — RoleExecutionStep is frozen
14. `test_all_role_methods_exist` — RoleExecutor has verify, synthesize, judge, challenge, fact_check methods

End with:
```python
if __name__ == "__main__":
    unittest.main()
```

## DONE WHEN
- [ ] `src/gracekelly/core/role_executor.py` exists with RoleExecutor class
- [ ] `tests/test_role_executor.py` exists with exactly 14 test methods
- [ ] `python -m pytest tests/test_role_executor.py -q` → 14 passed, 0 failed
- [ ] `python -m pytest -q` → all existing tests still pass (631+)
- [ ] No other files created or modified

## SELF-EVALUATION
After completing, score yourself 1-10. Target: 9.8/10.
```
