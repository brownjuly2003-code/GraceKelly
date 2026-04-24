from __future__ import annotations

import asyncio
import json
import unittest
from collections.abc import Callable
from types import SimpleNamespace
from typing import Any, cast

from fastapi import FastAPI, Request
from pydantic import ValidationError

from gracekelly.api.routes import batch, compare, consensus, debate, pipeline, smart, smart_v2, stream
from gracekelly.core.contracts import StepStatus
from gracekelly.core.execution_profile import resolve_execution_profile
from gracekelly.schemas import OrchestrateRequest


class _ExecutionResult:
    def __init__(self, *, output_text: str, model_id: str) -> None:
        self.status = StepStatus.COMPLETED
        self.output_text = output_text
        self.failure_code = None
        self.failure_message = None
        self.duration_ms = 1
        self.input_tokens = 1
        self.output_tokens = 1
        self.model_id = model_id


class _ApiAdapter:
    async def execute_async(self, exec_request: Any) -> _ExecutionResult:
        return self.execute(exec_request)

    def execute(self, exec_request: Any) -> _ExecutionResult:
        return _ExecutionResult(
            output_text="[provider_unavailable] OpenAI API key is not configured.",
            model_id=exec_request.step.model.id,
        )


class _DryRunAdapter:
    async def execute_async(self, exec_request: Any) -> _ExecutionResult:
        return self.execute(exec_request)

    def execute(self, exec_request: Any) -> _ExecutionResult:
        if exec_request.plan.dry_run:
            text = f"[dry-run] Simulated response for: {exec_request.prompt}"
        else:
            text = "[provider_unavailable] dry_run flag was not propagated."
        return _ExecutionResult(output_text=text, model_id=exec_request.step.model.id)


class _TaskRepository:
    backend_name = "memory"

    def save_task_with_steps(self, task: object, steps: list[object]) -> None:
        return None


class DryRunPropagationTests(unittest.TestCase):
    def _request(self, *, embeddings_client: object | None = object()) -> Request:
        app = FastAPI()
        app.state.api_adapters = {"openai": _ApiAdapter()}
        app.state.dry_run_adapter = _DryRunAdapter()
        app.state.execution_profile = resolve_execution_profile("dry-run")
        app.state.embeddings_client = embeddings_client
        app.state.task_repository = _TaskRepository()
        return cast(Request, SimpleNamespace(app=app))

    def _assert_dry_run_text(self, text: str) -> None:
        self.assertIn("[dry-run]", text)
        self.assertNotIn("[provider_unavailable]", text)
        self.assertNotIn("OpenAI API key is not configured", text)

    def test_compare_uses_dry_run(self) -> None:
        payload = compare.CompareRequest(
            prompt="compare prompt",
            models=["claude-sonnet-4-6", "claude-sonnet-4-6"],
            analyze=True,
            dry_run=True,
        )

        response = asyncio.run(compare.run_compare(payload, self._request()))

        self.assertEqual(response.succeeded, 2)
        self._assert_dry_run_text(response.answers[0].answer)
        self.assertIsNotNone(response.analysis)
        self._assert_dry_run_text(response.analysis or "")

    def test_consensus_uses_dry_run_without_embeddings(self) -> None:
        payload = consensus.ConsensusRequest(
            prompt="consensus prompt",
            model="claude-sonnet-4-6",
            variations_per_round=3,
            dry_run=True,
        )

        response = consensus.run_consensus(payload, self._request(embeddings_client=None))

        self.assertEqual(response.consensus_score, 1.0)
        self.assertEqual(response.total_llm_calls, 3)
        self._assert_dry_run_text(response.best_response)

    def test_debate_uses_dry_run(self) -> None:
        payload = debate.DebateRequest(
            topic="debate topic",
            model="claude-sonnet-4-6",
            dry_run=True,
        )

        response = asyncio.run(debate.run_debate_endpoint(payload, self._request()))

        self._assert_dry_run_text(response.initial_position)
        self._assert_dry_run_text(response.challenge)
        self._assert_dry_run_text(response.defense)
        self._assert_dry_run_text(response.improved_response)

    def test_smart_uses_dry_run(self) -> None:
        payload = smart.SmartRequest(
            prompt="hello",
            model="claude-sonnet-4-6",
            dry_run=True,
        )

        response = asyncio.run(smart.run_smart(payload, self._request()))

        self._assert_dry_run_text(response.answer)

    def test_smart_uses_dry_run_execution_profile(self) -> None:
        payload = smart.SmartRequest(
            prompt="hello",
            model="claude-sonnet-4-6",
        )

        response = asyncio.run(smart.run_smart(payload, self._request()))

        self._assert_dry_run_text(response.answer)

    def test_smart_v2_uses_dry_run(self) -> None:
        payload = smart_v2.SmartV2Request(
            prompt="hello",
            model="claude-sonnet-4-6",
            dry_run=True,
        )

        response = asyncio.run(smart_v2.run_smart_v2(payload, self._request()))

        self._assert_dry_run_text(response.answer)

    def test_batch_uses_dry_run(self) -> None:
        payload = batch.BatchRequest(
            prompts=["a", "b"],
            model="claude-sonnet-4-6",
            dry_run=True,
        )

        response = asyncio.run(batch.run_batch(payload, self._request()))

        self.assertEqual(response.succeeded, 2)
        self._assert_dry_run_text(response.results[0].answer)
        self._assert_dry_run_text(response.results[1].answer)

    def test_pipeline_uses_dry_run(self) -> None:
        payload = pipeline.PipelineRequest(
            prompt="hello",
            model="claude-sonnet-4-6",
            dry_run=True,
        )

        response = asyncio.run(pipeline.run_pipeline(payload, self._request()))

        self._assert_dry_run_text(response.answer)

    def test_stream_complete_event_contains_task_id(self) -> None:
        body = OrchestrateRequest(
            prompt="stream test",
            model="claude-sonnet-4-6",
            reasoning=False,
            dry_run=True,
        )

        response = asyncio.run(stream.orchestrate_stream(self._request(), body))

        async def collect() -> list[str]:
            chunks: list[str] = []
            async for chunk in response.body_iterator:
                chunks.append(chunk if isinstance(chunk, str) else bytes(chunk).decode())
            return chunks

        payload = "".join(asyncio.run(collect()))
        complete_data = next(line for line in payload.splitlines() if line.startswith("data: "))
        event = json.loads(complete_data.removeprefix("data: "))

        self.assertTrue(event["task_id"])

    def test_request_models_accept_dry_run(self) -> None:
        cases: list[Callable[[], object]] = [
            lambda: compare.CompareRequest(prompt="compare prompt", models=["claude-sonnet-4-6"], dry_run=True),
            lambda: consensus.ConsensusRequest(prompt="consensus prompt", model="claude-sonnet-4-6", dry_run=True),
            lambda: debate.DebateRequest(topic="debate topic", model="claude-sonnet-4-6", dry_run=True),
            lambda: smart.SmartRequest(prompt="hello", model="claude-sonnet-4-6", dry_run=True),
            lambda: smart_v2.SmartV2Request(prompt="hello", model="claude-sonnet-4-6", dry_run=True),
            lambda: batch.BatchRequest(prompts=["a"], model="claude-sonnet-4-6", dry_run=True),
            lambda: pipeline.PipelineRequest(prompt="hello", model="claude-sonnet-4-6", dry_run=True),
        ]

        for factory in cases:
            with self.subTest(factory=factory):
                try:
                    factory()
                except ValidationError as exc:  # pragma: no cover - intended to fail before implementation
                    self.fail(str(exc))
