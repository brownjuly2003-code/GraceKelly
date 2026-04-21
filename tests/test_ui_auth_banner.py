from __future__ import annotations

import json
import threading
from collections.abc import Generator
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

import pytest

STATIC_DIR = Path(__file__).resolve().parents[1] / "static"


class _QuietStaticHandler(SimpleHTTPRequestHandler):
    def log_message(self, format: str, *args: object) -> None:
        return


def _json_response(route: Any, payload: object, *, status: int = 200) -> None:
    route.fulfill(
        status=status,
        content_type="application/json",
        body=json.dumps(payload),
    )


def _sse_response(route: Any, events: list[tuple[str, dict[str, object]]]) -> None:
    body = "".join(
        f"event: {event}\ndata: {json.dumps(payload)}\n\n"
        for event, payload in events
    )
    route.fulfill(status=200, content_type="text/event-stream", body=body)


@pytest.fixture()
def static_server() -> Generator[str, None, None]:
    handler = partial(_QuietStaticHandler, directory=str(STATIC_DIR))
    server = ThreadingHTTPServer(("127.0.0.1", 0), handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield f"http://127.0.0.1:{server.server_port}"
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)


@pytest.fixture()
def page() -> Generator[Any, None, None]:
    playwright_sync = pytest.importorskip("playwright.sync_api")
    with playwright_sync.sync_playwright() as playwright:
        try:
            browser = playwright.chromium.launch()
        except Exception as exc:  # pragma: no cover - environment-dependent
            pytest.skip(f"Playwright Chromium browser is not installed: {exc}")
        context = browser.new_context(viewport={"width": 1280, "height": 800})
        page = context.new_page()
        try:
            yield page
        finally:
            context.close()
            browser.close()


def test_sync_auth_banner_shows_server_message_and_trace_id(static_server: str, page: Any) -> None:
    def handle_api(route: Any) -> None:
        path = urlparse(route.request.url).path
        if path == "/api/v1/health":
            _json_response(route, {"status": "ok"})
            return
        if path == "/api/v1/models":
            _json_response(
                route,
                {
                    "models": [
                        {"id": "Kimi K2", "model_id": "Kimi K2", "display_name": "Kimi K2"},
                    ]
                },
            )
            return
        if path == "/api/v1/orchestrate" and route.request.method == "POST":
            _json_response(
                route,
                {
                    "detail": {
                        "code": "model_auth_required",
                        "message": "Session expired on the server.",
                        "trace_id": "sync-trace-123",
                    }
                },
                status=503,
            )
            return
        _json_response(route, {})

    page.route("**/api/v1/**", handle_api)
    page.goto(static_server)
    page.evaluate(
        """
        async () => {
          try {
            await window.api.post("/api/v1/orchestrate", { prompt: "sync auth" });
          } catch (_error) {
          }
        }
        """
    )

    page.wait_for_selector("#auth-banner:not(.hidden)")
    banner_text = page.locator("#auth-banner").inner_text()

    assert "Session expired on the server." in banner_text
    assert "sync-trace-123" in banner_text


def test_async_auth_banner_shows_task_failure_message_and_trace_id(static_server: str, page: Any) -> None:
    def handle_api(route: Any) -> None:
        path = urlparse(route.request.url).path
        if path == "/api/v1/health":
            _json_response(route, {"status": "ok"})
            return
        if path == "/api/v1/models":
            _json_response(
                route,
                {
                    "models": [
                        {"id": "Kimi K2", "model_id": "Kimi K2", "display_name": "Kimi K2"},
                    ]
                },
            )
            return
        if path == "/api/v1/orchestrate/stream" and route.request.method == "POST":
            _sse_response(
                route,
                [
                    ("accepted", {"model_id": "Kimi K2", "task_id": "task-auth-1"}),
                    ("complete", {"model_id": "Kimi K2", "task_id": "task-auth-1", "text": ""}),
                ],
            )
            return
        if path == "/api/v1/tasks/task-auth-1":
            _json_response(
                route,
                {
                    "task_id": "task-auth-1",
                    "status": "failed",
                    "execution_mode": "browser",
                    "failure_code": "auth_failed",
                    "failure_message": "Async auth failure from task polling.",
                    "metadata": {"trace_id": "async-trace-456"},
                    "steps": [
                        {"step_index": 1, "status": "failed", "failure_code": "auth_failed"},
                    ],
                },
            )
            return
        _json_response(route, {})

    page.route("**/api/v1/**", handle_api)
    page.goto(static_server)
    page.locator("#query-input").fill("show async auth banner")
    page.locator("#btn-submit").click()

    page.wait_for_selector("#auth-banner:not(.hidden)")
    banner_text = page.locator("#auth-banner").inner_text()

    assert "Async auth failure from task polling." in banner_text
    assert "async-trace-456" in banner_text


def test_auth_banner_retry_resubmits_request_and_hides_on_success(static_server: str, page: Any) -> None:
    stream_requests = 0

    def handle_api(route: Any) -> None:
        nonlocal stream_requests
        path = urlparse(route.request.url).path
        if path == "/api/v1/health":
            _json_response(route, {"status": "ok"})
            return
        if path == "/api/v1/models":
            _json_response(
                route,
                {
                    "models": [
                        {"id": "Kimi K2", "model_id": "Kimi K2", "display_name": "Kimi K2"},
                    ]
                },
            )
            return
        if path == "/api/v1/orchestrate/stream" and route.request.method == "POST":
            stream_requests += 1
            task_id = f"task-retry-{stream_requests}"
            _sse_response(
                route,
                [
                    ("accepted", {"model_id": "Kimi K2", "task_id": task_id}),
                    ("complete", {"model_id": "Kimi K2", "task_id": task_id, "text": ""}),
                ],
            )
            return
        if path == "/api/v1/tasks/task-retry-1":
            _json_response(
                route,
                {
                    "task_id": "task-retry-1",
                    "status": "failed",
                    "execution_mode": "browser",
                    "failure_code": "auth_failed",
                    "failure_message": "Retry required after auth loss.",
                    "metadata": {"trace_id": "retry-trace-001"},
                    "steps": [
                        {"step_index": 1, "status": "failed", "failure_code": "auth_failed"},
                    ],
                },
            )
            return
        if path == "/api/v1/tasks/task-retry-2":
            _json_response(
                route,
                {
                    "task_id": "task-retry-2",
                    "status": "completed",
                    "execution_mode": "browser",
                    "output_text": "Recovered after retry.",
                    "metadata": {"trace_id": "retry-trace-002"},
                    "steps": [
                        {"step_index": 1, "status": "completed", "output_text": "Recovered after retry."},
                    ],
                },
            )
            return
        _json_response(route, {})

    page.route("**/api/v1/**", handle_api)
    page.goto(static_server)
    page.locator("#query-input").fill("retry auth banner")
    page.locator("#btn-submit").click()

    page.wait_for_selector("#auth-banner:not(.hidden)")
    page.wait_for_function("() => !document.getElementById('auth-banner-retry').disabled")
    page.locator("#auth-banner-retry").click()
    page.wait_for_function("() => document.getElementById('auth-banner').classList.contains('hidden')")

    assert stream_requests == 2
    assert page.locator("#auth-banner").get_attribute("class") is not None
    assert "Recovered after retry." in page.locator("#chat-area").inner_text()
