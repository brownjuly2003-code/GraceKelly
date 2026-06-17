from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

import httpx

Status = Literal["PASS", "FAIL", "SKIP"]

DEFAULT_GRACEKELLY_URL = "http://127.0.0.1:8011"
DEFAULT_RAG_URL = "http://127.0.0.1:8000"
REQUEST_TIMEOUT_SECONDS = 10.0
SUBPROCESS_STDOUT_LINES = 30
SUBPROCESS_TIMEOUT_SECONDS = 90.0

RAG_SMOKE_PATH = Path("D:/RAG_Support_Assistant/scripts/gracekelly_smoke.py")
AGENT_TOOLKIT_DIR = Path("D:/agent_toolkit")
JUHUB_DIR = Path("D:/Perplexity_Orchestrator2")
JUHUB_SCHEDULER_PATH = JUHUB_DIR / "juhub" / "backend" / "scheduler.py"

SMART_PAYLOAD: Mapping[str, object] = {"prompt": "2+2", "dry_run": True}
ORCHESTRATE_PAYLOAD: Mapping[str, object] = {
    "prompt": "2+2",
    "model": "claude-sonnet-4-6",
    "reliability_level": "quick",
    "dry_run": True,
}
SMART_FORBIDDEN_MARKERS = ("provider_unavailable", "Mistral")


@dataclass(frozen=True)
class CliConfig:
    gracekelly_url: str
    rag_url: str
    skip_rag: bool
    skip_agent_toolkit: bool
    skip_juhub: bool
    verbose: bool


@dataclass(frozen=True)
class StepResult:
    step: str
    component: str
    status: Status
    detail: str
    output: str = ""


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run GraceKelly V2 ecosystem smoke checks.")
    parser.add_argument("--gracekelly-url", default=DEFAULT_GRACEKELLY_URL)
    parser.add_argument("--rag-url", default=DEFAULT_RAG_URL)
    parser.add_argument("--skip-rag", action="store_true")
    parser.add_argument("--skip-agent-toolkit", action="store_true")
    parser.add_argument("--skip-juhub", action="store_true")
    parser.add_argument("--verbose", action="store_true")
    return parser.parse_args(list(argv) if argv is not None else None)


def build_config(args: argparse.Namespace) -> CliConfig:
    return CliConfig(
        gracekelly_url=str(args.gracekelly_url).rstrip("/"),
        rag_url=str(args.rag_url).rstrip("/"),
        skip_rag=bool(args.skip_rag),
        skip_agent_toolkit=bool(args.skip_agent_toolkit),
        skip_juhub=bool(args.skip_juhub),
        verbose=bool(args.verbose),
    )


def check_gracekelly_ready(client: httpx.Client, base_url: str) -> bool:
    try:
        response = client.get(f"{base_url}/healthz/ready")
    except httpx.HTTPError:
        return False
    return response.status_code == 200


def run_v2_smart(client: httpx.Client, base_url: str) -> StepResult:
    try:
        response = client.post(f"{base_url}/api/v1/smart", json=dict(SMART_PAYLOAD))
    except httpx.HTTPError as exc:
        return StepResult("1.1", "V2 /smart", "FAIL", f"request failed: {exc}")

    body = response_json(response)
    model_id = string_value(body.get("model_id"))
    answer = string_value(body.get("answer"))
    failures: list[str] = []
    if response.status_code != 200:
        failures.append(f"status={response.status_code}")
    if not model_id:
        failures.append("model_id missing")
    elif model_id == "mistral-small":
        failures.append("model=mistral-small")
    if not answer:
        failures.append("answer missing")
    for marker in SMART_FORBIDDEN_MARKERS:
        if marker in answer:
            failures.append(f"answer contains {marker}")
    if failures:
        return StepResult("1.1", "V2 /smart", "FAIL", "; ".join(failures))
    return StepResult("1.1", "V2 /smart", "PASS", f"model={model_id}")


def run_v2_orchestrate(client: httpx.Client, base_url: str) -> StepResult:
    try:
        response = client.post(f"{base_url}/api/v1/orchestrate", json=dict(ORCHESTRATE_PAYLOAD))
    except httpx.HTTPError as exc:
        return StepResult("1.2", "V2 /orchestrate", "FAIL", f"request failed: {exc}")

    body = response_json(response)
    status = string_value(body.get("status"))
    execution_mode = string_value(body.get("execution_mode"))
    failures: list[str] = []
    if response.status_code != 200:
        failures.append(f"status_code={response.status_code}")
    if status != "completed":
        failures.append(f"status={status or '<missing>'}")
    if execution_mode != "dry-run":
        failures.append(f"execution_mode={execution_mode or '<missing>'}")
    if failures:
        return StepResult("1.2", "V2 /orchestrate", "FAIL", "; ".join(failures))
    return StepResult("1.2", "V2 /orchestrate", "PASS", "status=completed")


def run_rag_smoke(client: httpx.Client, config: CliConfig) -> StepResult:
    if config.skip_rag:
        return StepResult("2", "RAG smoke", "SKIP", "disabled by --skip-rag")
    if not RAG_SMOKE_PATH.exists():
        return StepResult("2", "RAG smoke", "SKIP", "RAG smoke harness not found")
    if not http_reachable(client, config.rag_url):
        return StepResult("2", "RAG smoke", "SKIP", "RAG :8000 not reachable")

    completed = run_subprocess(["python", str(RAG_SMOKE_PATH)])
    stdout_tail = last_lines(completed.stdout or "", SUBPROCESS_STDOUT_LINES)
    summary = find_summary_line(stdout_tail, ("pass", "fail", "skip"))
    detail = summary or f"exit={completed.returncode}"
    status: Status = "PASS" if completed.returncode == 0 else "FAIL"
    if status == "FAIL" and summary:
        detail = f"exit={completed.returncode}; {summary}"
    return StepResult("2", "RAG smoke", status, detail, combined_output(completed))


def run_agent_toolkit_smoke(config: CliConfig) -> StepResult:
    if config.skip_agent_toolkit:
        return StepResult("3", "agent_toolkit", "SKIP", "disabled by --skip-agent-toolkit")
    if not AGENT_TOOLKIT_DIR.exists():
        return StepResult("3", "agent_toolkit", "SKIP", "agent_toolkit not found")
    integration_dir = AGENT_TOOLKIT_DIR / "tests" / "integration"
    if not integration_dir.exists():
        return StepResult("3", "agent_toolkit", "SKIP", "integration tests not found")
    if shutil.which("uv") is None:
        return StepResult("3", "agent_toolkit", "SKIP", "uv not found")

    completed = run_subprocess(
        ["uv", "run", "pytest", "tests/integration/", "-q", "--no-header"],
        cwd=AGENT_TOOLKIT_DIR,
    )
    output = combined_output(completed)
    summary = find_summary_line(output, (" passed", " failed", " skipped", " error"))
    detail = summary or f"exit={completed.returncode}"
    status: Status = "PASS" if completed.returncode == 0 else "FAIL"
    if status == "FAIL" and summary:
        detail = f"exit={completed.returncode}; {summary}"
    return StepResult("3", "agent_toolkit", status, detail, output)


def run_juhub_smoke(config: CliConfig) -> StepResult:
    if config.skip_juhub:
        return StepResult("4", "juhub debate", "SKIP", "disabled by --skip-juhub")
    if not JUHUB_DIR.exists() or not JUHUB_SCHEDULER_PATH.exists():
        return StepResult("4", "juhub debate", "SKIP", "scheduler not present")

    env = dict(os.environ)
    env["GK_DRY_RUN"] = "1"
    command = ["python", "-m", "juhub.backend.scheduler", "--now", "--dry-run"]
    completed = run_subprocess(command, cwd=JUHUB_DIR, env=env)
    output = combined_output(completed)
    fallback_used = False
    if completed.returncode != 0 and dry_run_flag_unsupported(output):
        fallback_used = True
        completed = run_subprocess(["python", "-m", "juhub.backend.scheduler", "--now"], cwd=JUHUB_DIR, env=env)
        output = output + "\n" + combined_output(completed)

    if completed.returncode == 0:
        detail = "dry-run ok"
        if fallback_used:
            detail = "dry-run env fallback ok"
        return StepResult("4", "juhub debate", "PASS", detail, output)
    detail = f"exit={completed.returncode}"
    summary = last_nonempty_line(output)
    if summary:
        detail = f"{detail}; {summary}"
    return StepResult("4", "juhub debate", "FAIL", detail, output)


def run_all(config: CliConfig, client: httpx.Client) -> list[StepResult]:
    return [
        run_v2_smart(client, config.gracekelly_url),
        run_v2_orchestrate(client, config.gracekelly_url),
        run_rag_smoke(client, config),
        run_agent_toolkit_smoke(config),
        run_juhub_smoke(config),
    ]


def response_json(response: httpx.Response) -> dict[str, object]:
    try:
        payload: object = response.json()
    except ValueError:
        return {}
    if not isinstance(payload, dict):
        return {}
    result: dict[str, object] = {}
    for key, value in payload.items():
        if isinstance(key, str):
            result[key] = value
    return result


def string_value(value: object) -> str:
    if value is None:
        return ""
    if isinstance(value, str):
        return value
    return str(value)


def http_reachable(client: httpx.Client, url: str) -> bool:
    try:
        client.get(url)
    except httpx.HTTPError:
        return False
    return True


def run_subprocess(
    command: Sequence[str],
    *,
    cwd: Path | None = None,
    env: Mapping[str, str] | None = None,
) -> subprocess.CompletedProcess[str]:
    command_list = list(command)
    try:
        return subprocess.run(
            command_list,
            cwd=str(cwd) if cwd is not None else None,
            env=dict(env) if env is not None else None,
            capture_output=True,
            text=True,
            check=False,
            timeout=SUBPROCESS_TIMEOUT_SECONDS,
        )
    except subprocess.TimeoutExpired as exc:
        stdout = timeout_output_text(exc.output)
        stderr = timeout_output_text(exc.stderr)
        timeout_line = f"timed out after {SUBPROCESS_TIMEOUT_SECONDS:g}s"
        stderr = "\n".join(part for part in (stderr, timeout_line) if part)
        return subprocess.CompletedProcess(command_list, 124, stdout=stdout, stderr=stderr)


def timeout_output_text(value: str | bytes | None) -> str:
    if value is None:
        return ""
    if isinstance(value, bytes):
        return value.decode(errors="replace")
    return value


def combined_output(completed: subprocess.CompletedProcess[str]) -> str:
    parts = [completed.stdout or "", completed.stderr or ""]
    return "\n".join(part for part in parts if part)


def last_lines(text: str, count: int) -> str:
    return "\n".join(text.splitlines()[-count:])


def last_nonempty_line(text: str) -> str:
    for line in reversed(text.splitlines()):
        stripped = line.strip()
        if stripped:
            return stripped
    return ""


def find_summary_line(text: str, markers: Sequence[str]) -> str:
    for line in reversed(text.splitlines()):
        lowered = line.lower()
        if any(marker in lowered for marker in markers):
            return line.strip().strip("=")
    return last_nonempty_line(text)


def dry_run_flag_unsupported(text: str) -> bool:
    lowered = text.lower()
    if "--dry-run" not in lowered:
        return False
    return "unrecognized" in lowered or "no such option" in lowered or "unknown option" in lowered


def print_step_line(result: StepResult) -> None:
    print(f"{result.status}: {result.step} {result.component} - {result.detail}")


def print_summary(results: Sequence[StepResult]) -> None:
    headers = ("Step", "Component", "Status", "Detail")
    rows = [(result.step, result.component, result.status, result.detail) for result in results]
    widths = [
        max(len(headers[index]), *(len(row[index]) for row in rows))
        for index in range(len(headers))
    ]
    print()
    print(" | ".join(headers[index].ljust(widths[index]) for index in range(len(headers))))
    for row in rows:
        print(" | ".join(row[index].ljust(widths[index]) for index in range(len(headers))))


def print_verbose_output(result: StepResult) -> None:
    if not result.output:
        return
    print()
    print(f"--- {result.step} {result.component} output ---")
    print(result.output.rstrip())


def main(argv: Sequence[str] | None = None) -> int:
    config = build_config(parse_args(argv))
    with httpx.Client(timeout=REQUEST_TIMEOUT_SECONDS) as client:
        if not check_gracekelly_ready(client, config.gracekelly_url):
            print("ERROR: GraceKelly :8011 not reachable, boot uvicorn first")
            return 1
        results = run_all(config, client)

    for result in results:
        print_step_line(result)
        if config.verbose:
            print_verbose_output(result)
    print_summary(results)
    return 1 if any(result.status == "FAIL" for result in results) else 0


if __name__ == "__main__":
    sys.exit(main())
