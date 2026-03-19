from __future__ import annotations

_TEMPLATES: tuple[str, ...] = (
    "{prompt}",
    "Explain step by step: {prompt}",
    "Consider multiple perspectives on: {prompt}",
    "What are the key facts about: {prompt}",
    "Provide a detailed analysis of: {prompt}",
    "Summarize the current understanding of: {prompt}",
    "What would experts say about: {prompt}",
    "Break down the following topic: {prompt}",
    "Give a comprehensive answer to: {prompt}",
)


def generate_variations(prompt: str, count: int = 3) -> list[str]:
    if not prompt or not prompt.strip():
        raise ValueError("Prompt must not be empty.")
    results: list[str] = []
    for i in range(count):
        template = _TEMPLATES[i % len(_TEMPLATES)]
        results.append(template.format(prompt=prompt))
    return results
