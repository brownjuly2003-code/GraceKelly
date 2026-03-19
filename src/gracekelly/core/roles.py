from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum


class RoleType(StrEnum):
    VERIFIER = "verifier"
    SYNTHESIZER = "synthesizer"
    JUDGE = "judge"
    DEVIL_ADVOCATE = "devil_advocate"
    FACT_VERIFIER = "fact_verifier"
    DECOMPOSER = "decomposer"


@dataclass(frozen=True, slots=True)
class Role:
    role_type: RoleType
    system_prompt: str
    preferred_models: tuple[str, ...]
    reasoning_required: bool


ROLES: dict[RoleType, Role] = {
    RoleType.VERIFIER: Role(
        role_type=RoleType.VERIFIER,
        system_prompt="You are a verification specialist. Review the given answer for accuracy, completeness, and logical consistency. Identify any unsupported claims, missing context, or logical errors. Provide a structured assessment with specific issues found.",
        preferred_models=("claude-sonnet-4-6-api", "gpt-5-4-api"),
        reasoning_required=True,
    ),
    RoleType.SYNTHESIZER: Role(
        role_type=RoleType.SYNTHESIZER,
        system_prompt="You are a synthesis specialist. Combine multiple answers into one coherent, comprehensive response. Preserve the strongest points from each source while eliminating redundancy. The final answer should be better than any individual input.",
        preferred_models=("claude-sonnet-4-6-api",),
        reasoning_required=True,
    ),
    RoleType.JUDGE: Role(
        role_type=RoleType.JUDGE,
        system_prompt="You are an impartial quality judge. Evaluate the given answer on a scale of 1-10 across these dimensions: factual accuracy, completeness, clarity, and relevance. Provide specific scores and brief justification for each dimension.",
        preferred_models=("gpt-5-4-api", "claude-sonnet-4-6-api"),
        reasoning_required=True,
    ),
    RoleType.DEVIL_ADVOCATE: Role(
        role_type=RoleType.DEVIL_ADVOCATE,
        system_prompt="You are a devil's advocate. Challenge the given answer by finding weaknesses, counterarguments, and edge cases. Your goal is to stress-test the reasoning, not to be contrarian. Highlight genuine vulnerabilities.",
        preferred_models=("gpt-5-4-api",),
        reasoning_required=True,
    ),
    RoleType.FACT_VERIFIER: Role(
        role_type=RoleType.FACT_VERIFIER,
        system_prompt="You are a fact-checking specialist. Examine each factual claim in the given answer. For each claim, assess whether it is verifiable, likely accurate, potentially misleading, or demonstrably false. Flag any claims that require citations.",
        preferred_models=("claude-sonnet-4-6-api", "gpt-5-4-api"),
        reasoning_required=True,
    ),
    RoleType.DECOMPOSER: Role(
        role_type=RoleType.DECOMPOSER,
        system_prompt="You are a task decomposition specialist. Break down the given complex question into independent, answerable sub-questions. Each sub-question should be self-contained and contribute to answering the original question. Return a numbered list.",
        preferred_models=("claude-sonnet-4-6-api",),
        reasoning_required=True,
    ),
}


def get_role(role_type: RoleType) -> Role:
    return ROLES[role_type]


def format_prompt_with_role(role: Role, user_prompt: str) -> dict[str, str]:
    return {"system": role.system_prompt, "user": user_prompt}
