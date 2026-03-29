# Skills Evaluation Report

Date: 2026-03-19

## Summary

| Skill | Installs | Actionability | Specificity | Token Eff. | Conflict | Verdict |
|-------|----------|---------------|-------------|------------|----------|---------|
| softaworks/agent-toolkit@codex | 3.4K | 8/10 | 7/10 | 4/10 | medium | EVALUATE_FURTHER |
| rysweet/amplihack@roadmap-strategist | 109 | 6/10 | 6/10 | 3/10 | high | SKIP |
| rookie-ricardo/erduo-skills@gemini-watermark-remover | 1.4K | 9/10 | 9/10 | 9/10 | high | ADOPT |

## 1. softaworks/agent-toolkit@codex

**What it does**: Adds a Codex-focused operator skill for Claude-style agents. It tells the agent how to launch `codex exec`, choose model/reasoning/sandbox flags, resume sessions, and summarize output back to the user.
**Key strengths**:
- Concrete command patterns, not abstract advice.
- Clear mapping from task type to sandbox mode.
- Includes resume workflow and follow-up behavior.
**Weaknesses**:
- Heavy for a single operational skill: about 758 words in `SKILL.md`.
- Bakes in brittle assumptions like always using `--skip-git-repo-check` and `2>/dev/null`.
- References agent-specific primitives like `AskUserQuestion`, so it is not portable as-is.
- Installer flagged it with higher marketplace risk than the other evaluated skills.
**Conflicts with**: partial overlap with `codex-task`; one prepares Codex-ready tasks, this one executes Codex CLI sessions
**Verdict**: EVALUATE_FURTHER — useful and actionable, but it needs trimming and a pass to remove harness-specific assumptions before broad adoption.

## 2. rysweet/amplihack@roadmap-strategist

**What it does**: Maintains a project roadmap in `.pm/roadmap.md`, tracks goal progress, aligns backlog work with goals, and produces strategic recommendations. It is positioned as a long-horizon PM/strategy helper.
**Key strengths**:
- Gives a concrete file-based roadmap format instead of vague planning talk.
- Includes simple progress and alignment formulas that an agent can actually apply.
- Has clear triggers around goals, milestones, and strategic direction.
**Weaknesses**:
- Installation failed on Windows during checkout because the repository contains an invalid path `:memory:`.
- Very verbose for the value delivered: about 1019 words in the reviewed skill file.
- Overlaps strongly with existing planning skills while adding another persistent state convention under `.pm/`.
- Strategic guidance is reasonable but generic; the real differentiator is mostly the markdown template.
**Conflicts with**: `research-driven-planning`, `writing-plans`
**Verdict**: SKIP — the Windows installation failure alone is enough to block adoption, and the skill does not add enough unique value over the planning stack already installed.

## 3. rookie-ricardo/erduo-skills@gemini-watermark-remover

**What it does**: Removes the visible bottom-right Gemini watermark from images using reverse alpha blending and pre-captured watermark maps. It ships a focused CLI, two watermark assets, and a short algorithm note.
**Key strengths**:
- Extremely concrete: install Pillow, run one script, get one output file.
- Highly specific to a real agent weakness; this is not generic image-processing advice.
- Compact and efficient: about 191 words in `SKILL.md`, with the real detail pushed into code and `references/algorithm.md`.
- The bundled script and algorithm note are coherent and implement a real reversible compositing approach.
**Weaknesses**:
- Narrow scope: only the visible Gemini watermark in the expected bottom-right layout.
- Depends on the current watermark pattern and shipped alpha maps.
- Separate standalone skill may duplicate discoverability with an existing broader watermark skill.
**Conflicts with**: `watermark-remove`
**Verdict**: ADOPT — strong specialized value, concise instructions, and a real algorithm. Best outcome is to keep it or merge its Gemini-specific logic into `watermark-remove`.

## Recommendations

- Keep `gemini-watermark-remover`. If you want fewer overlapping commands, fold its algorithm and assets into `watermark-remove` instead of dropping it.
- Do not adopt `roadmap-strategist` in its current form. The Windows install breakage and overlap with `research-driven-planning` and `writing-plans` make it a bad fit.
- Put `codex` in a probation bucket rather than promoting it immediately. It is useful for Claude-to-Codex delegation, but it should be shortened and de-harnessed first.
- Installation note: `npx skills add ... -g -y` installed successful skills into `~/.agents/skills` and symlinked them into Claude-compatible locations, not directly into `~/.claude/skills`.
- Verification note: `roadmap-strategist` was evaluated from the repository skill file after install failed, so the content review is valid but the install status remains failed on this Windows environment.
