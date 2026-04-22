"""Live SMART end-to-end smoke against a running uvicorn + Perplexity Pro profile.

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
from datetime import datetime
from pathlib import Path
from typing import Any

import httpx
from playwright.sync_api import sync_playwright

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


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--prompt", default=DEFAULT_PROMPT)
    parser.add_argument("--ascii-fallback", action="store_true", help="Use ASCII prompt instead of cyrillic.")
    parser.add_argument("--outdir", default=".workflow/outbox")
    parser.add_argument("--tag", default=f"smoke-{datetime.utcnow().strftime('%Y%m%d-%H%M%S')}")
    parser.add_argument("--timeout", type=int, default=360, help="Outer wait budget in seconds.")
    return parser.parse_args()


def check_uvicorn_alive() -> bool:
    try:
        response = httpx.get(f"{BASE_URL}/health", timeout=5.0)
    except httpx.HTTPError:
        return False
    return response.status_code == 200


def select_smart_pattern(page: Any) -> bool:
    trigger = page.locator("#model-trigger").first
    trigger.wait_for(state="visible", timeout=10_000)
    trigger.click()
    popup = page.locator("#model-popup").first
    popup.wait_for(state="visible", timeout=5_000)
    # Click the .model-item whose label contains "Умный выбор".
    smart_item = page.locator(".model-item", has_text="Умный выбор").first
    smart_item.wait_for(state="visible", timeout=5_000)
    smart_item.click()
    return True


def submit_prompt(page: Any, prompt: str) -> None:
    query_input = page.locator("#query-input").first
    query_input.wait_for(state="visible", timeout=10_000)
    query_input.click()
    query_input.fill(prompt)
    page.locator("#btn-submit").first.click()


def wait_for_smart_response(page: Any, timeout_seconds: int) -> dict[str, Any] | None:
    # Poll the network for the /api/v1/smart response body.
    deadline = time.monotonic() + timeout_seconds
    captured: dict[str, Any] = {}

    def _on_response(response: Any) -> None:
        if "/api/v1/smart" in response.url and response.request.method == "POST" and not captured:
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


def evaluate(response: dict[str, Any] | None) -> tuple[bool, list[str]]:
    reasons: list[str] = []
    if response is None:
        return False, ["No /api/v1/smart response captured within timeout"]
    if response.get("status_code") != 200:
        reasons.append(f"status_code={response.get('status_code')}")
    body = response.get("body_json") or {}
    answer = str(body.get("answer") or body.get("output_text") or "")
    if len(answer) < 500:
        reasons.append(f"answer too short ({len(answer)} chars, need >=500)")
    for marker in FORBIDDEN_MARKERS:
        if marker in answer:
            reasons.append(f"forbidden marker present: {marker!r}")
    if not any(keyword in answer for keyword in TOPIC_KEYWORDS):
        reasons.append("no topic keyword found (Europe/China/USA/adoption/subsidies)")
    return len(reasons) == 0, reasons


def write_report(outdir: Path, tag: str, ok: bool, reasons: list[str], prompt: str, duration_s: float) -> None:
    lines = [
        f"# Live SMART smoke — {tag}",
        "",
        f"Status: {'success' if ok else 'failure'}",
        f"Prompt: {prompt!r}",
        f"Duration: {duration_s:.1f}s",
        "",
        "## Evaluation",
    ]
    if ok:
        lines.append("- meaningful EV answer returned, no forbidden markers")
    else:
        for reason in reasons:
            lines.append(f"- {reason}")
    (outdir / f"{tag}-SMART-report.md").write_text("\n".join(lines), encoding="utf-8")


def main() -> int:
    args = parse_args()
    prompt = ASCII_FALLBACK_PROMPT if args.ascii_fallback else args.prompt
    outdir = Path(args.outdir)
    outdir.mkdir(parents=True, exist_ok=True)

    if not check_uvicorn_alive():
        print(f"ERROR: uvicorn not responding at {BASE_URL}. Start it first.", file=sys.stderr)
        return 1

    started = time.monotonic()
    response_payload: dict[str, Any] | None = None

    with sync_playwright() as playwright:
        # Separate bundled chromium drives only the local SPA. The real Perplexity
        # flow runs inside uvicorn's own Playwright instance against chrome-profile/.
        browser = playwright.chromium.launch(headless=False)
        context = browser.new_context(viewport={"width": 1280, "height": 800}, locale="ru-RU")
        page = context.new_page()
        try:
            page.goto(BASE_URL, wait_until="domcontentloaded")
            page.wait_for_timeout(2_000)
            page.screenshot(path=str(outdir / f"{args.tag}-SMART-before.png"), full_page=False)
            if not select_smart_pattern(page):
                print("ERROR: could not open model menu to select 'Умный выбор'", file=sys.stderr)
                return 1
            submit_prompt(page, prompt)
            response_payload = wait_for_smart_response(page, timeout_seconds=args.timeout)
            page.wait_for_timeout(1_000)
            page.screenshot(path=str(outdir / f"{args.tag}-SMART-after.png"), full_page=False)
        finally:
            context.close()
            browser.close()

    (outdir / f"{args.tag}-SMART-response.json").write_text(
        json.dumps(response_payload or {}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    ok, reasons = evaluate(response_payload)
    duration = time.monotonic() - started
    write_report(outdir, args.tag, ok, reasons, prompt, duration)
    print(f"{'OK' if ok else 'FAIL'} — {args.tag} — {duration:.1f}s", file=sys.stderr)
    for reason in reasons:
        print(f"  · {reason}", file=sys.stderr)
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
