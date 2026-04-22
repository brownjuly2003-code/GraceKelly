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
SAMPLE_ATTACHMENT = Path(__file__).resolve().parent / "fixtures" / "sample-attachment.txt"
MODELS_PAYLOAD = {
    "models": [
        {"id": "sonar", "model_id": "sonar", "display_name": "Sonar"},
        {"id": "best", "model_id": "best", "display_name": "Best"},
        {"id": "claude-sonnet-4-6", "model_id": "claude-sonnet-4-6", "display_name": "Claude 4.6"},
        {"id": "gpt-5-4", "model_id": "gpt-5-4", "display_name": "GPT-5.4"},
        {"id": "gemini-3-1-pro", "model_id": "gemini-3-1-pro", "display_name": "Gemini 3.1"},
        {"id": "kimi-k2-5", "model_id": "kimi-k2-5", "display_name": "Kimi K2.5"},
    ]
}


class _QuietStaticHandler(SimpleHTTPRequestHandler):
    def log_message(self, format: str, *args: object) -> None:
        return


def _json_response(route: Any, payload: object, *, status: int = 200) -> None:
    route.fulfill(
        status=status,
        content_type="application/json",
        body=json.dumps(payload),
    )


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


def test_ui_upload_flow_drives_orchestrate_upload(static_server: str, page: Any) -> None:
    captured: dict[str, str] = {}

    def handle_api(route: Any) -> None:
        path = urlparse(route.request.url).path
        if path == "/api/v1/health":
            _json_response(route, {"status": "ok"})
            return
        if path == "/api/v1/models":
            _json_response(route, MODELS_PAYLOAD)
            return
        if path == "/api/v1/orchestrate/upload" and route.request.method == "POST":
            captured["content_type"] = route.request.headers.get("content-type", "")
            captured["body"] = route.request.post_data or ""
            _json_response(
                route,
                {
                    "output_text": "Upload synthesis ready.",
                    "task_id": "task-upload-1",
                    "status": "completed",
                    "model_id": "best",
                },
            )
            return
        _json_response(route, {})

    page.route("**/api/v1/**", handle_api)
    page.goto(static_server)
    page.wait_for_selector("#model-trigger")
    page.locator("#model-trigger").click()
    page.locator("#model-popup").get_by_text("Best", exact=True).evaluate(
        "(element) => element.closest('.model-item').click()"
    )
    page.locator("#file-input").set_input_files(str(SAMPLE_ATTACHMENT))
    page.locator("#query-input").fill("Summarize attachment")
    page.locator("#btn-submit").click()
    page.wait_for_function(
        "() => document.getElementById('chat-area').innerText.includes('Upload synthesis ready.')"
    )

    assert captured["content_type"].startswith("multipart/form-data; boundary=")
    assert 'name="prompt"' in captured["body"]
    assert "Summarize attachment" in captured["body"]
    assert 'name="model"' in captured["body"]
    assert "best" in captured["body"]
    assert 'name="session_id"' in captured["body"]
    assert 'name="files"' in captured["body"]
    assert "sample-attachment.txt" in captured["body"]
    assert "Upload synthesis ready." in page.locator("#chat-area").inner_text()


def test_ui_smart_decomposition_flow(static_server: str, page: Any) -> None:
    captured: dict[str, object] = {}

    def handle_api(route: Any) -> None:
        path = urlparse(route.request.url).path
        if path == "/api/v1/health":
            _json_response(route, {"status": "ok"})
            return
        if path == "/api/v1/models":
            _json_response(route, MODELS_PAYLOAD)
            return
        if path == "/api/v1/smart" and route.request.method == "POST":
            captured["body"] = json.loads(route.request.post_data or "{}")
            _json_response(
                route,
                {
                    "answer": "Smart decomposition ready.",
                    "task_id": "task-smart-1",
                    "status": "completed",
                    "model_id": "smart-router",
                },
            )
            return
        _json_response(route, {})

    prompt = "сделай ресёрч по рынку X"

    page.route("**/api/v1/**", handle_api)
    page.goto(static_server)
    page.wait_for_selector("#model-trigger")
    page.locator("#model-trigger").click()
    page.locator("#model-popup").get_by_text("Умный выбор", exact=True).evaluate(
        "(element) => element.closest('.model-item').click()"
    )
    assert page.evaluate("() => window.modelMenu.getSelection().pattern") == "smart"
    assert page.evaluate("() => window.modelMenu.getSelection().model") == "best"

    page.locator("#query-input").fill(prompt)
    page.locator("#btn-submit").click()
    page.wait_for_function(
        "() => document.getElementById('chat-area').innerText.includes('Smart decomposition ready.')"
    )

    assert captured["body"] == {"prompt": prompt, "model": "best"}
    assert "Smart decomposition ready." in page.locator("#chat-area").inner_text()


def test_ui_debate_flow(static_server: str, page: Any) -> None:
    captured: dict[str, object] = {}

    def handle_api(route: Any) -> None:
        path = urlparse(route.request.url).path
        if path == "/api/v1/health":
            _json_response(route, {"status": "ok"})
            return
        if path == "/api/v1/models":
            _json_response(route, MODELS_PAYLOAD)
            return
        if path == "/api/v1/debate" and route.request.method == "POST":
            captured["body"] = json.loads(route.request.post_data or "{}")
            _json_response(
                route,
                {
                    "improved_response": "Debate synthesis ready.",
                    "task_id": "task-debate-1",
                    "status": "completed",
                    "model_id": "debate-engine",
                },
            )
            return
        _json_response(route, {})

    topic = "почему Perplexity вытесняет OpenAI"

    page.route("**/api/v1/**", handle_api)
    page.goto(static_server)
    page.wait_for_selector("#model-trigger")
    page.locator("#model-trigger").click()
    page.locator("#model-popup").get_by_text("Дебаты", exact=True).evaluate(
        "(element) => element.closest('.model-item').click()"
    )
    assert page.evaluate("() => window.modelMenu.getSelection().pattern") == "debate"
    assert page.evaluate("() => window.modelMenu.getSelection().model") == "best"

    page.locator("#query-input").fill(topic)
    page.locator("#btn-submit").click()
    page.wait_for_function(
        "() => document.getElementById('chat-area').innerText.includes('Debate synthesis ready.')"
    )

    assert captured["body"] == {"topic": topic, "model": "best"}
    assert "Debate synthesis ready." in page.locator("#chat-area").inner_text()


def _test_smart_menu_item_does_not_emit_null_model_legacy(static_server: str, page: Any) -> None:
    captured: dict[str, object] = {}

    def handle_api(route: Any) -> None:
        path = urlparse(route.request.url).path
        if path == "/api/v1/health":
            _json_response(route, {"status": "ok"})
            return
        if path == "/api/v1/models":
            _json_response(route, MODELS_PAYLOAD)
            return
        if path == "/api/v1/smart" and route.request.method == "POST":
            captured["body"] = json.loads(route.request.post_data or "{}")
            _json_response(
                route,
                {
                    "answer": "Smart decomposition ready.",
                    "task_id": "task-smart-2",
                    "status": "completed",
                    "model_id": "smart-router",
                },
            )
            return
        _json_response(route, {})

    page.route("**/api/v1/**", handle_api)
    page.goto(static_server)
    page.wait_for_selector("#model-trigger")
    page.locator("#model-trigger").click()
    page.locator("#model-popup").get_by_text("Ð£Ð¼Ð½Ñ‹Ð¹ Ð²Ñ‹Ð±Ð¾Ñ€", exact=True).evaluate(
        "(element) => element.closest('.model-item').click()"
    )
    page.locator("#query-input").fill("check model contract")
    page.locator("#btn-submit").click()
    page.wait_for_function(
        "() => document.getElementById('chat-area').innerText.includes('Smart decomposition ready.')"
    )

    assert isinstance(captured["body"], dict)
    assert captured["body"]["model"] is not None
    assert captured["body"]["model"] != ""


def test_smart_menu_item_does_not_emit_null_model(static_server: str, page: Any) -> None:
    captured: dict[str, object] = {}

    def handle_api(route: Any) -> None:
        path = urlparse(route.request.url).path
        if path == "/api/v1/health":
            _json_response(route, {"status": "ok"})
            return
        if path == "/api/v1/models":
            _json_response(route, MODELS_PAYLOAD)
            return
        if path == "/api/v1/smart" and route.request.method == "POST":
            captured["body"] = json.loads(route.request.post_data or "{}")
            _json_response(
                route,
                {
                    "answer": "Smart decomposition ready.",
                    "task_id": "task-smart-3",
                    "status": "completed",
                    "model_id": "smart-router",
                },
            )
            return
        _json_response(route, {})

    page.route("**/api/v1/**", handle_api)
    page.goto(static_server)
    page.wait_for_selector("#model-trigger")
    page.evaluate(
        """() => {
            window.modelMenu.currentItemId = "smart";
            window.modelMenu._build();
            window.modelMenu._emitSelection();
        }"""
    )
    page.locator("#query-input").fill("check model contract")
    page.locator("#btn-submit").click()
    page.wait_for_function(
        "() => document.getElementById('chat-area').innerText.includes('Smart decomposition ready.')"
    )

    assert isinstance(captured["body"], dict)
    assert captured["body"]["model"] is not None
    assert captured["body"]["model"] != ""
