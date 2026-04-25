from __future__ import annotations

import io
import subprocess
import sys
import tempfile
import unittest
from collections.abc import Mapping, Sequence
from contextlib import redirect_stdout
from pathlib import Path
from types import TracebackType
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import ecosystem_smoke as smoke


class FakeResponse:
    def __init__(self, status_code: int, payload: Mapping[str, object] | None = None) -> None:
        self.status_code = status_code
        self._payload = dict(payload or {})
        self.text = ""

    def json(self) -> dict[str, object]:
        return self._payload


class FakeClient:
    def __init__(self, get_responses: Sequence[FakeResponse], post_responses: Sequence[FakeResponse]) -> None:
        self._get_responses = list(get_responses)
        self._post_responses = list(post_responses)
        self.gets: list[str] = []
        self.posts: list[tuple[str, dict[str, object]]] = []

    def __enter__(self) -> FakeClient:
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        return None

    def get(self, url: str) -> FakeResponse:
        self.gets.append(url)
        return self._get_responses.pop(0)

    def post(self, url: str, *, json: Mapping[str, object]) -> FakeResponse:
        self.posts.append((url, dict(json)))
        return self._post_responses.pop(0)


class FakeRunner:
    def __init__(self, results: Sequence[subprocess.CompletedProcess[str]]) -> None:
        self._results = list(results)
        self.calls: list[tuple[list[str], str | None, Mapping[str, str] | None]] = []

    def __call__(
        self,
        args: Sequence[str],
        *,
        cwd: str | None = None,
        env: Mapping[str, str] | None = None,
        capture_output: bool = False,
        text: bool = False,
        check: bool = False,
        timeout: float | None = None,
    ) -> subprocess.CompletedProcess[str]:
        self.calls.append((list(args), cwd, env))
        return self._results.pop(0)


class TimeoutRunner:
    def __init__(self) -> None:
        self.calls: list[list[str]] = []

    def __call__(
        self,
        args: Sequence[str],
        *,
        cwd: str | None = None,
        env: Mapping[str, str] | None = None,
        capture_output: bool = False,
        text: bool = False,
        check: bool = False,
        timeout: float | None = None,
    ) -> subprocess.CompletedProcess[str]:
        self.calls.append(list(args))
        raise subprocess.TimeoutExpired(cmd=list(args), timeout=timeout or 0.0, output="partial stdout")


def _completed(returncode: int, stdout: str = "", stderr: str = "") -> subprocess.CompletedProcess[str]:
    return subprocess.CompletedProcess(args=["cmd"], returncode=returncode, stdout=stdout, stderr=stderr)


def _run_main(argv: Sequence[str]) -> tuple[int, str]:
    output = io.StringIO()
    with redirect_stdout(output):
        exit_code = smoke.main(argv)
    return exit_code, output.getvalue()


class EcosystemSmokeTests(unittest.TestCase):
    def test_all_steps_pass_and_summary_returns_zero(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            rag_smoke = root / "rag" / "scripts" / "gracekelly_smoke.py"
            rag_smoke.parent.mkdir(parents=True)
            rag_smoke.write_text("", encoding="utf-8")
            agent_project = root / "agent_toolkit"
            (agent_project / "tests" / "integration").mkdir(parents=True)
            juhub_project = root / "Perplexity_Orchestrator2"
            scheduler = juhub_project / "juhub" / "backend" / "scheduler.py"
            scheduler.parent.mkdir(parents=True)
            scheduler.write_text("", encoding="utf-8")

            client = FakeClient(
                get_responses=[FakeResponse(200), FakeResponse(404)],
                post_responses=[
                    FakeResponse(200, {"model_id": "claude-sonnet-4-6", "answer": "4"}),
                    FakeResponse(200, {"status": "completed", "execution_mode": "dry-run"}),
                ],
            )
            runner = FakeRunner(
                [
                    _completed(0, "setup\n3 PASS / 5 SKIP / 0 FAIL\n"),
                    _completed(0, "76 passed, 2 skipped in 1.00s\n"),
                    _completed(0, "debate dry-run ok\n"),
                ]
            )

            def fake_client_factory(*, timeout: float) -> FakeClient:
                return client

            def fake_which(name: str) -> str | None:
                return "C:/uv.exe" if name == "uv" else None

            with (
                patch("ecosystem_smoke.httpx.Client", fake_client_factory),
                patch("ecosystem_smoke.subprocess.run", runner),
                patch("ecosystem_smoke.shutil.which", fake_which),
                patch.object(smoke, "RAG_SMOKE_PATH", rag_smoke),
                patch.object(smoke, "AGENT_TOOLKIT_DIR", agent_project),
                patch.object(smoke, "JUHUB_DIR", juhub_project),
                patch.object(smoke, "JUHUB_SCHEDULER_PATH", scheduler),
            ):
                exit_code, output = _run_main(["--gracekelly-url", "http://gk", "--rag-url", "http://rag"])

            self.assertEqual(0, exit_code)
            self.assertIn("Step | Component", output)
            self.assertIn("V2 /smart", output)
            self.assertIn("agent_toolkit", output)
            self.assertIn("juhub debate", output)
            self.assertEqual({"prompt": "2+2", "dry_run": True}, client.posts[0][1])
            self.assertEqual(3, len(runner.calls))

    def test_one_failed_step_returns_one(self) -> None:
        client = FakeClient(
            get_responses=[FakeResponse(200)],
            post_responses=[
                FakeResponse(200, {"model_id": "mistral-small", "answer": "provider_unavailable Mistral"}),
                FakeResponse(200, {"status": "completed", "execution_mode": "dry-run"}),
            ],
        )

        def fake_client_factory(*, timeout: float) -> FakeClient:
            return client

        with patch("ecosystem_smoke.httpx.Client", fake_client_factory):
            exit_code, output = _run_main(["--skip-rag", "--skip-agent-toolkit", "--skip-juhub"])

        self.assertEqual(1, exit_code)
        self.assertIn("FAIL", output)
        self.assertIn("mistral-small", output)

    def test_missing_external_projects_are_skipped_and_exit_zero(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            client = FakeClient(
                get_responses=[FakeResponse(200)],
                post_responses=[
                    FakeResponse(200, {"model_id": "claude-sonnet-4-6", "answer": "4"}),
                    FakeResponse(200, {"status": "completed", "execution_mode": "dry-run"}),
                ],
            )
            runner = FakeRunner([])

            def fake_client_factory(*, timeout: float) -> FakeClient:
                return client

            with (
                patch("ecosystem_smoke.httpx.Client", fake_client_factory),
                patch("ecosystem_smoke.subprocess.run", runner),
                patch.object(smoke, "RAG_SMOKE_PATH", root / "missing" / "gracekelly_smoke.py"),
                patch.object(smoke, "AGENT_TOOLKIT_DIR", root / "missing-agent"),
                patch.object(smoke, "JUHUB_DIR", root / "missing-juhub"),
                patch.object(smoke, "JUHUB_SCHEDULER_PATH", root / "missing-juhub" / "scheduler.py"),
            ):
                exit_code, output = _run_main([])

            self.assertEqual(0, exit_code)
            self.assertIn("RAG smoke", output)
            self.assertIn("SKIP", output)
            self.assertIn("agent_toolkit not found", output)
            self.assertIn("scheduler not present", output)
            self.assertEqual([], runner.calls)

    def test_timed_out_external_step_fails_with_summary(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            juhub_project = root / "Perplexity_Orchestrator2"
            scheduler = juhub_project / "juhub" / "backend" / "scheduler.py"
            scheduler.parent.mkdir(parents=True)
            scheduler.write_text("", encoding="utf-8")
            client = FakeClient(
                get_responses=[FakeResponse(200)],
                post_responses=[
                    FakeResponse(200, {"model_id": "claude-sonnet-4-6", "answer": "4"}),
                    FakeResponse(200, {"status": "completed", "execution_mode": "dry-run"}),
                ],
            )
            runner = TimeoutRunner()

            def fake_client_factory(*, timeout: float) -> FakeClient:
                return client

            with (
                patch("ecosystem_smoke.httpx.Client", fake_client_factory),
                patch("ecosystem_smoke.subprocess.run", runner),
                patch.object(smoke, "JUHUB_DIR", juhub_project),
                patch.object(smoke, "JUHUB_SCHEDULER_PATH", scheduler),
            ):
                exit_code, output = _run_main(["--skip-rag", "--skip-agent-toolkit"])

            self.assertEqual(1, exit_code)
            self.assertIn("juhub debate", output)
            self.assertIn("timed out", output)
            self.assertEqual(1, len(runner.calls))


if __name__ == "__main__":
    unittest.main()
