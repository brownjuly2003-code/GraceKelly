from __future__ import annotations

from gracekelly.core.task_graph import SubTask, TaskGraph


def build_sequential(prompts: list[str]) -> TaskGraph:
    graph = TaskGraph()
    prev_id = ""
    for i, prompt in enumerate(prompts):
        task_id = f"step-{i}"
        deps = (prev_id,) if prev_id else ()
        graph.add_task(SubTask(id=task_id, prompt=prompt, dependencies=deps))
        prev_id = task_id
    return graph


def build_parallel(prompts: list[str]) -> TaskGraph:
    graph = TaskGraph()
    for i, prompt in enumerate(prompts):
        graph.add_task(SubTask(id=f"parallel-{i}", prompt=prompt))
    return graph


def build_fan_out_fan_in(prompts: list[str], synthesis_prompt: str) -> TaskGraph:
    graph = TaskGraph()
    fan_ids = []
    for i, prompt in enumerate(prompts):
        task_id = f"fan-{i}"
        graph.add_task(SubTask(id=task_id, prompt=prompt))
        fan_ids.append(task_id)
    graph.add_task(SubTask(
        id="synthesis",
        prompt=synthesis_prompt,
        dependencies=tuple(fan_ids),
    ))
    return graph


def build_pipeline(stages: list[list[str]]) -> TaskGraph:
    graph = TaskGraph()
    prev_stage_ids: list[str] = []
    for stage_idx, prompts in enumerate(stages):
        current_ids = []
        for task_idx, prompt in enumerate(prompts):
            task_id = f"stage-{stage_idx}-task-{task_idx}"
            deps = tuple(prev_stage_ids) if prev_stage_ids else ()
            graph.add_task(SubTask(id=task_id, prompt=prompt, dependencies=deps))
            current_ids.append(task_id)
        prev_stage_ids = current_ids
    return graph
