from __future__ import annotations

import asyncio
import unittest
from concurrent.futures import ThreadPoolExecutor
from types import SimpleNamespace
from unittest.mock import patch

from fastapi import Response

from gracekelly.core.contracts import TaskStatus
from gracekelly.schemas import OrchestrateRequest


class PlaywrightThreadingTests(unittest.TestCase):
    def test_browser_executor_created_on_app_state(self) -> None:
        from gracekelly.main import create_app

        app = create_app()
        executor = getattr(app.state, "browser_executor", None)
        try:
            self.assertIsInstance(executor, ThreadPoolExecutor)
            self.assertEqual(getattr(executor, "_max_workers", None), 1)
        finally:
            if executor is not None:
                executor.shutdown(wait=False)

    def test_orchestrate_uses_browser_executor_for_submit_snapshot(self) -> None:
        from gracekelly.api.routes import orchestrate as orchestrate_module

        payload = OrchestrateRequest(prompt="hello", models=["dry-run"], dry_run=True)
        browser_executor = ThreadPoolExecutor(max_workers=1)
        snapshot = SimpleNamespace(
            task=SimpleNamespace(
                task_id="task-1",
                status="succeeded",
                execution_mode="dry-run",
                adapter_hint=None,
                dry_run=True,
                model_count=1,
            ),
            steps=[],
        )
        service = SimpleNamespace(submit_snapshot=lambda request: snapshot)
        state = SimpleNamespace(
            orchestrator_service=service,
            settings=SimpleNamespace(orchestrate_timeout_seconds=None),
            browser_executor=browser_executor,
        )
        request = SimpleNamespace(app=SimpleNamespace(state=state))
        response = Response()
        sentinel = object()

        class FakeLoop:
            def __init__(self) -> None:
                self.executor = None
                self.fn = None
                self.args: tuple[object, ...] = ()

            def run_in_executor(self, executor: object, fn: object, *args: object) -> object:
                self.executor = executor
                self.fn = fn
                self.args = args

                async def _result() -> object:
                    return snapshot

                return _result()

        fake_loop = FakeLoop()

        async def run_test() -> object:
            with (
                patch.object(orchestrate_module.asyncio, "get_running_loop", return_value=fake_loop),
                patch.object(orchestrate_module, "_requested_models_from_request", return_value=[]),
                patch.object(orchestrate_module.OrchestrateResponse, "from_task", return_value=sentinel),
            ):
                return await orchestrate_module.orchestrate(payload, request, response)

        try:
            result = asyncio.run(run_test())
            self.assertIs(result, sentinel)
            self.assertIs(fake_loop.executor, browser_executor)
            self.assertIs(fake_loop.fn, service.submit_snapshot)
            self.assertEqual(fake_loop.args, (payload,))
        finally:
            browser_executor.shutdown(wait=False)

    def test_retry_uses_browser_executor_for_submit_snapshot(self) -> None:
        from gracekelly.api.routes import orchestrate as orchestrate_module

        browser_executor = ThreadPoolExecutor(max_workers=1)
        snapshot = SimpleNamespace(
            task=SimpleNamespace(task_id="task-2"),
            steps=[],
        )
        original = SimpleNamespace(status=TaskStatus.FAILED)
        retry_request = OrchestrateRequest(prompt="hello", models=["dry-run"], dry_run=True)
        service = SimpleNamespace(
            get_task=lambda task_id: original,
            list_task_steps=lambda task_id: [],
            list_task_events=lambda task_id: [],
            submit_snapshot=lambda request, retry_of_task_id=None: snapshot,
        )
        state = SimpleNamespace(orchestrator_service=service, browser_executor=browser_executor)
        request = SimpleNamespace(app=SimpleNamespace(state=state))
        sentinel = object()

        class FakeLoop:
            def __init__(self) -> None:
                self.executor = None
                self.fn = None
                self.args: tuple[object, ...] = ()

            def run_in_executor(self, executor: object, fn: object, *args: object) -> object:
                self.executor = executor
                self.fn = fn
                self.args = args

                async def _result() -> object:
                    return snapshot

                return _result()

        fake_loop = FakeLoop()

        async def run_test() -> object:
            with (
                patch.object(orchestrate_module.asyncio, "get_running_loop", return_value=fake_loop),
                patch.object(orchestrate_module, "_build_retry_request", return_value=retry_request),
                patch.object(orchestrate_module, "_requested_models_from_request", return_value=[]),
                patch.object(orchestrate_module.OrchestrateResponse, "from_task", return_value=sentinel),
            ):
                return await orchestrate_module.retry_task(request, "task-1")

        try:
            result = asyncio.run(run_test())
            self.assertIs(result, sentinel)
            self.assertIs(fake_loop.executor, browser_executor)
            self.assertEqual(fake_loop.args, ())
            self.assertIs(fake_loop.fn.func, service.submit_snapshot)
            self.assertEqual(fake_loop.fn.args, (retry_request,))
            self.assertEqual(fake_loop.fn.keywords, {"retry_of_task_id": "task-1"})
        finally:
            browser_executor.shutdown(wait=False)
