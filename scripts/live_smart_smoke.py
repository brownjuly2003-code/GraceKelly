"""Live SMART/DEBATE end-to-end smoke against uvicorn + Perplexity Pro profile.

Preconditions (script does not start these for you):
  1. uvicorn on http://127.0.0.1:8011 launched with the live profile env:
       GRACEKELLY_BROWSER_ENABLED=true
       GRACEKELLY_BROWSER_AUTOMATION_BACKEND=playwright
       GRACEKELLY_BROWSER_PROFILE_DIR=<path>/chrome-profile
       GRACEKELLY_EXECUTION_PROFILE=hybrid
       GRACEKELLY_BROWSER_CALL_TIMEOUT_SECONDS=120
       PYTHONUTF8=1
  2. No other chrome.exe is using chrome-profile (kill stale PIDs first).
  3. The profile is already signed in to Perplexity Pro.

Usage:
    .venv/Scripts/python.exe scripts/live_smart_smoke.py \
        [--prompt "..."] [--outdir .workflow/outbox] [--tag smoke-NN]

Exit codes:
    0 — SMART returned 200 with a meaningful answer matching topic keywords
    1 — anything else (timeout, auth_failed, mismatch, non-200, empty answer)

Artifacts written to <outdir>/:
    <tag>-SMART-response.json    — status_code, headers, body_json, duration_ms
    <tag>-SMART-before.png       — SPA before submit (1280x800)
    <tag>-SMART-after.png        — SPA after response lands (1280x800)
    <tag>-SMART-report.md        — human-readable pass/fail + hypothesis trace
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import httpx

DEFAULT_PROMPT = (
    "Сравни рынки EV в Европе, США и Китае по ключевым метрикам: "
    "adoption rate, charger coverage, subsidies — верни структурированный обзор."
)
ASCII_FALLBACK_PROMPT = (
    "Compare EV markets in Europe, USA and China across key metrics: "
    "adoption rate, charger coverage, subsidies — return a structured overview."
)
TOPIC_KEYWORDS = ("Europe", "China", "USA", "Европе", "Китае", "adoption", "subsidies")
FORBIDDEN_MARKERS = (
    "[auth_failed]",
    "[provider_unavailable]",
    "Ask a follow-up",
    "Thinking",
)
BASE_URL = "http://127.0.0.1:8011"
PATTERN_MENU_LABEL = {"smart": "Умный выбор", "debate": "Дебаты"}
PATTERN_API_PATH = {"smart": "/api/v1/smart", "debate": "/api/v1/debate"}
CONSENSUS_PROMPT = (
    "Name 3 leading EV manufacturers in China in 2024 with brief comments "
    "(1-2 sentences for each)."
)
COMPARE_PROMPT = (
    "Compare Claude Sonnet 4.6 and GPT-5.4 on mathematical reasoning ability. "
    "Return a structured assessment."
)
UPLOAD_PROMPT = "Briefly describe the attached file and highlight the key points."
PATTERN_CHOICES = ("smart", "debate", "consensus", "compare", "upload")
PATTERN_DEFAULT_PROMPT = {
    "smart": DEFAULT_PROMPT,
    "debate": DEFAULT_PROMPT,
    "consensus": CONSENSUS_PROMPT,
    "compare": COMPARE_PROMPT,
    "upload": UPLOAD_PROMPT,
}
PATTERN_ASCII_FALLBACK_PROMPT = {
    "smart": ASCII_FALLBACK_PROMPT,
    "debate": ASCII_FALLBACK_PROMPT,
    "consensus": CONSENSUS_PROMPT,
    "compare": COMPARE_PROMPT,
    "upload": UPLOAD_PROMPT,
}
PATTERN_MENU_LABEL = {
    "smart": "Умный выбор",
    "debate": "Дебаты",
    "consensus": None,
    "compare": None,
    "upload": None,
}
PATTERN_API_PATH = {
    "smart": "/api/v1/smart",
    "debate": "/api/v1/debate",
    "consensus": "/api/v1/consensus",
    "compare": "/api/v1/compare",
    "upload": "/api/v1/orchestrate/upload",
}
PATTERN_EVALUATION = {
    "smart": {
        "min_length": 500,
        "topic_keywords": ("Europe", "China", "USA", "Европе", "Китае", "adoption", "subsidies"),
        "answer_fields": ("answer", "output_text"),
    },
    "debate": {
        "min_length": 500,
        "topic_keywords": ("Europe", "China", "USA", "Европе", "Китае", "adoption", "subsidies"),
        "answer_fields": ("improved_response", "answer"),
    },
    "consensus": {
        "min_length": 300,
        "topic_keywords": ("электромобил", "производител", "Китае", "China"),
        "answer_fields": ("best_response", "consensus_text", "answer", "output_text"),
    },
    "compare": {
        "min_length": 400,
        "topic_keywords": ("Claude", "GPT", "reasoning"),
        "answer_fields": ("comparison", "analysis", "output_text"),
    },
    "upload": {
        "min_length": 150,
        "topic_keywords": (),
        "answer_fields": ("answer", "output_text"),
    },
}
DIRECT_POST_COMPARE_MODELS = (
    "best",
    "claude-sonnet-4-6",
    "gpt-5-4",
    "gemini-3-1-pro",
    "kimi-k2-5",
)
DIRECT_POST_CONSENSUS_MODEL = "best"
DIRECT_POST_UPLOAD_MODEL = "best"


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--pattern", choices=PATTERN_CHOICES, default="smart")
    parser.add_argument("--prompt", default=None)
    parser.add_argument("--attachment", default=None, help="Path to attachment for --pattern=upload.")
    parser.add_argument("--ascii-fallback", action="store_true", help="Use ASCII prompt instead of cyrillic.")
    parser.add_argument("--outdir", default=".workflow/outbox")
    parser.add_argument("--tag", default=f"smoke-{datetime.now(UTC).strftime('%Y%m%d-%H%M%S')}")
    parser.add_argument("--timeout", type=int, default=360, help="Outer wait budget in seconds.")
    args = parser.parse_args(argv)
    if args.prompt is None:
        args.prompt = PATTERN_DEFAULT_PROMPT[args.pattern]
    if args.pattern == "upload" and not args.attachment:
        parser.error("--attachment is required when --pattern=upload")
    if args.pattern != "upload" and args.attachment:
        print("WARNING: --attachment is ignored unless --pattern=upload", file=sys.stderr)
        args.attachment = None
    return args


def check_uvicorn_alive() -> bool:
    try:
        response = httpx.get(f"{BASE_URL}/health", timeout=5.0)
    except httpx.HTTPError:
        return False
    return response.status_code == 200


def select_pattern(page: Any, pattern: str) -> bool:
    menu_label = PATTERN_MENU_LABEL[pattern]
    if menu_label is None:
        return True
    trigger = page.locator("#model-trigger").first
    trigger.wait_for(state="visible", timeout=10_000)
    trigger.click()
    popup = page.locator("#model-popup").first
    popup.wait_for(state="visible", timeout=5_000)
    item = page.locator(".model-item", has_text=menu_label).first
    item.wait_for(state="visible", timeout=5_000)
    item.click()
    return True


def submit_prompt(page: Any, prompt: str) -> None:
    query_input = page.locator("#query-input").first
    query_input.wait_for(state="visible", timeout=10_000)
    query_input.click()
    query_input.fill(prompt)
    page.locator("#btn-submit").first.click()


def submit_upload(page: Any, prompt: str, attachment_path: str) -> bool:
    attachment_input = page.locator("#file-input").first
    try:
        attachment_input.wait_for(state="attached", timeout=2_000)
    except Exception:
        attachment_input = page.locator("input[type='file']").first
        try:
            attachment_input.wait_for(state="attached", timeout=2_000)
        except Exception:
            return False
    attachment_input.set_input_files(attachment_path)
    submit_prompt(page, prompt)
    return True


def submit_direct_request(pattern: str, prompt: str, timeout_seconds: int) -> dict[str, Any]:
    url = f"{BASE_URL}{PATTERN_API_PATH[pattern]}"
    if pattern == "consensus":
        response = httpx.post(
            url,
            json={"prompt": prompt, "model": DIRECT_POST_CONSENSUS_MODEL},
            timeout=timeout_seconds,
        )
    elif pattern == "compare":
        response = httpx.post(
            url,
            json={"prompt": prompt, "models": list(DIRECT_POST_COMPARE_MODELS), "analyze": True},
            timeout=timeout_seconds,
        )
    else:
        raise ValueError(f"Direct POST is not configured for pattern={pattern}")
    try:
        body = response.json()
    except Exception:
        body = {"__raw__": response.text}
    return {"status_code": response.status_code, "body_json": body}


def submit_upload_direct(prompt: str, attachment_path: str, timeout_seconds: int) -> dict[str, Any]:
    attachment = Path(attachment_path)
    with attachment.open("rb") as handle:
        response = httpx.post(
            f"{BASE_URL}{PATTERN_API_PATH['upload']}",
            data={"prompt": prompt, "model": DIRECT_POST_UPLOAD_MODEL},
            files={"files": (attachment.name, handle, "text/plain")},
            timeout=timeout_seconds,
        )
    try:
        body = response.json()
    except Exception:
        body = {"__raw__": response.text}
    return {"status_code": response.status_code, "body_json": body}


def wait_for_pattern_response(page: Any, pattern: str, timeout_seconds: int) -> dict[str, Any] | None:
    api_path = PATTERN_API_PATH[pattern]
    deadline = time.monotonic() + timeout_seconds
    captured: dict[str, Any] = {}

    def _on_response(response: Any) -> None:
        if api_path in response.url and response.request.method == "POST" and not captured:
            try:
                body = response.json()
            except Exception:
                body = {"__raw__": response.text()}
            captured["status_code"] = response.status
            captured["body_json"] = body

    page.on("response", _on_response)
    while time.monotonic() < deadline and not captured:
        page.wait_for_timeout(500)
    return captured or None


def evaluate(response: dict[str, Any] | None, pattern: str) -> tuple[bool, list[str]]:
    reasons: list[str] = []
    if response is None:
        return False, [f"No {PATTERN_API_PATH[pattern]} response captured within timeout"]
    rules = PATTERN_EVALUATION[pattern]
    if response.get("status_code") != 200:
        reasons.append(f"status_code={response.get('status_code')}")
    body = response.get("body_json") or {}
    answer_fields = rules["answer_fields"]
    answer = ""
    for field in answer_fields:
        value = body.get(field)
        if value:
            answer = str(value)
            break
    if not answer:
        reasons.append(f"answer field absent ({','.join(answer_fields)})")
    if len(answer) < rules["min_length"]:
        reasons.append(f"answer too short ({len(answer)} chars, need >={rules['min_length']})")
    for marker in FORBIDDEN_MARKERS:
        if marker in answer:
            reasons.append(f"forbidden marker present: {marker!r}")
    topic_keywords = rules["topic_keywords"]
    if topic_keywords and not any(keyword in answer for keyword in topic_keywords):
        reasons.append("no topic keyword found")
    return len(reasons) == 0, reasons


def write_report(
    outdir: Path,
    tag: str,
    ok: bool,
    reasons: list[str],
    prompt: str,
    duration_s: float,
    pattern: str,
    notes: list[str] | None = None,
) -> None:
    suffix = pattern.upper()
    lines = [
        f"# Live {suffix} smoke — {tag}",
        "",
        f"Status: {'success' if ok else 'failure'}",
        f"Prompt: {prompt!r}",
        f"Duration: {duration_s:.1f}s",
        "",
        "## Path",
    ]
    for note in notes or ["ui submit path"]:
        lines.append(f"- {note}")
    lines.extend(["", "## Evaluation"])
    if ok:
        lines.append("- answer satisfied the pattern-specific evaluator")
    else:
        for reason in reasons:
            lines.append(f"- {reason}")
    (outdir / f"{tag}-{suffix}-report.md").write_text("\n".join(lines), encoding="utf-8")


def main() -> int:
    args = parse_args()
    prompt = PATTERN_ASCII_FALLBACK_PROMPT[args.pattern] if args.ascii_fallback else args.prompt
    outdir = Path(args.outdir)
    outdir.mkdir(parents=True, exist_ok=True)

    if not check_uvicorn_alive():
        print(f"ERROR: uvicorn not responding at {BASE_URL}. Start it first.", file=sys.stderr)
        return 1

    started = time.monotonic()
    response_payload: dict[str, Any] | None = None
    submission_notes: list[str] = []

    # Imported lazily so this module is importable (e.g. for unit tests of evaluate())
    # without the optional `browser` extra installed.
    from playwright.sync_api import sync_playwright

    with sync_playwright() as playwright:
        # Separate bundled chromium drives only the local SPA. The real Perplexity
        # flow runs inside uvicorn's own Playwright instance against chrome-profile/.
        browser = playwright.chromium.launch(headless=False)
        context = browser.new_context(viewport={"width": 1280, "height": 800}, locale="ru-RU")
        page = context.new_page()
        try:
            page.goto(BASE_URL, wait_until="domcontentloaded")
            page.wait_for_timeout(2_000)
            suffix = args.pattern.upper()
            page.screenshot(path=str(outdir / f"{args.tag}-{suffix}-before.png"), full_page=False)
            if args.pattern in {"consensus", "compare"}:
                submission_notes.append("pattern not surfaced in UI; using direct POST fallback")
                response_payload = submit_direct_request(args.pattern, prompt, args.timeout)
            else:
                if not select_pattern(page, args.pattern):
                    print(
                        f"ERROR: could not open model menu to select '{PATTERN_MENU_LABEL[args.pattern]}'",
                        file=sys.stderr,
                    )
                    return 1
                if args.pattern == "upload":
                    if submit_upload(page, prompt, args.attachment):
                        submission_notes.append("ui composer attachment path")
                        response_payload = wait_for_pattern_response(page, args.pattern, timeout_seconds=args.timeout)
                    else:
                        submission_notes.append("attachment input unavailable; using direct POST fallback")
                        response_payload = submit_upload_direct(prompt, args.attachment, args.timeout)
                else:
                    submission_notes.append("ui submit path")
                    submit_prompt(page, prompt)
                    response_payload = wait_for_pattern_response(page, args.pattern, timeout_seconds=args.timeout)
            page.wait_for_timeout(1_000)
            page.screenshot(path=str(outdir / f"{args.tag}-{suffix}-after.png"), full_page=False)
        finally:
            context.close()
            browser.close()

    suffix = args.pattern.upper()
    (outdir / f"{args.tag}-{suffix}-response.json").write_text(
        json.dumps(response_payload or {}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    ok, reasons = evaluate(response_payload, args.pattern)
    duration = time.monotonic() - started
    write_report(outdir, args.tag, ok, reasons, prompt, duration, args.pattern, notes=submission_notes)
    print(f"{'OK' if ok else 'FAIL'} — {args.tag} — {duration:.1f}s", file=sys.stderr)
    for reason in reasons:
        print(f"  · {reason}", file=sys.stderr)
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
