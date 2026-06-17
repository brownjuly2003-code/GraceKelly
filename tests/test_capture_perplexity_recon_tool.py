from __future__ import annotations

import argparse
import json
import unittest
from collections.abc import Callable
from datetime import date
from pathlib import Path
from unittest.mock import patch

from gracekelly.adapters.browser.selectors import PerplexitySelectors
from gracekelly.tools import capture_perplexity_recon

_TMP_ROOT = Path(".workflow/tmp-tests")
_TMP_ROOT.mkdir(parents=True, exist_ok=True)


class _FakeLocator:
    def __init__(
        self,
        *,
        visible: bool = False,
        click: Callable[[], None] | None = None,
        inner_html: str = "",
        texts: list[str] | None = None,
        fill: Callable[[str], None] | None = None,
        press_sequentially: Callable[[str], None] | None = None,
    ) -> None:
        self._visible = visible
        self._click = click
        self._inner_html = inner_html
        self._texts = texts or []
        self._fill = fill
        self._press_sequentially = press_sequentially
        self.first = self

    def is_visible(self) -> bool:
        return self._visible

    def count(self) -> int:
        return 1 if self._visible or self._inner_html or self._texts else 0

    def click(self, **kwargs: object) -> None:
        if self._click is not None:
            self._click()

    def inner_html(self) -> str:
        return self._inner_html

    def all_inner_texts(self) -> list[str]:
        return list(self._texts)

    def fill(self, value: str) -> None:
        if self._fill is not None:
            self._fill(value)
            return
        raise RuntimeError("fill not configured")

    def press_sequentially(self, value: str) -> None:
        if self._press_sequentially is not None:
            self._press_sequentially(value)
            return
        raise RuntimeError("press_sequentially not configured")


class _FakePage:
    def __init__(self) -> None:
        self.goto_calls: list[tuple[str, str]] = []
        self.screenshot_paths: list[str] = []
        self.more_open = False
        self.model_menu_open = False
        self.response_ready = False
        self.body = "Type @ for connectors and sources\nType / for search modes"
        self.composer_html = "<div>composer</div>"
        self.main_html = "<div>main</div>"
        self.model_menu_attrs = [
            {
                "tag": "button",
                "role": "menuitem",
                "aria_label": "Best",
                "aria_selected": None,
                "data_state": None,
                "data_testid": None,
                "class_list": ["menu-item", "best-item"],
                "text": "Best",
                "outer_html": '<button aria-label="Best">Best</button>',
                "parent_tag": "div",
                "bounding_box": {"x": 12, "y": 34, "width": 160, "height": 32},
            },
            {
                "tag": "button",
                "role": "menuitem",
                "aria_label": "Sonar",
                "aria_selected": False,
                "data_state": "inactive",
                "data_testid": "sonar-option",
                "class_list": ["menu-item", "sonar-item"],
                "text": "Sonar",
                "outer_html": '<button aria-label="Sonar">Sonar</button>',
                "parent_tag": "div",
                "bounding_box": {"x": 12, "y": 70, "width": 160, "height": 32},
            },
            {
                "tag": "button",
                "role": "menuitem",
                "aria_label": "Claude Sonnet 4.6",
                "aria_selected": False,
                "data_state": "inactive",
                "data_testid": "claude-sonnet-option",
                "class_list": ["menu-item", "claude-item"],
                "text": "Claude Sonnet 4.6",
                "outer_html": '<button aria-label="Claude Sonnet 4.6">Claude Sonnet 4.6</button>',
                "parent_tag": "div",
                "bounding_box": {"x": 12, "y": 106, "width": 160, "height": 32},
            },
        ]
        self.prompt_value = ""
        self.keyboard = _FakeKeyboard()

    def goto(self, url: str, wait_until: str) -> None:
        self.goto_calls.append((url, wait_until))

    def screenshot(self, *, path: str, full_page: bool) -> None:
        Path(path).write_text(f"screenshot:{full_page}", encoding="utf-8")
        self.screenshot_paths.append(path)

    def evaluate(self, script: str) -> list[object] | bool:
        if "querySelectorAll('button')" in script:
            if self.more_open:
                return ["More::More", "Model::Model", "Submit::Submit"]
            return ["New Thread", "More::More", "Submit::Submit"]
        if "getBoundingClientRect()" in script:
            if self.model_menu_open:
                return list(self.model_menu_attrs)
            return []
        if "document.querySelector(selector)" in script:
            return True
        raise AssertionError(f"Unexpected script: {script}")

    def locator(self, selector: str) -> _FakeLocator:
        if selector == 'div#ask-input[role="textbox"][contenteditable="true"]':
            return _FakeLocator(visible=True, click=lambda: None, fill=self._set_prompt, press_sequentially=self._set_prompt)
        if selector == "form":
            return _FakeLocator(visible=True, inner_html=self.composer_html)
        if selector == "main":
            return _FakeLocator(visible=True, inner_html=self.main_html)
        if 'aria-label="Model"' in selector or 'aria-haspopup="menu"' in selector:
            return _FakeLocator(visible=self.more_open, click=self._open_model_menu)
        if selector == 'button[aria-label="More"]':
            return _FakeLocator(visible=True, click=self._open_more)
        if selector == 'button:has-text("More")':
            return _FakeLocator(visible=True, click=self._open_more)
        if selector == 'button[aria-label="Submit"]':
            return _FakeLocator(visible=True, click=self._submit_prompt)
        if selector in ("main article", 'main [data-message-author-role="assistant"]', "main div.prose", 'main [class*="prose"]'):
            texts = ["OK"] if self.response_ready else []
            return _FakeLocator(visible=self.response_ready, texts=texts)
        if selector in ('[data-radix-popper-content-wrapper]', '[role="dialog"]', '[role="listbox"]'):
            texts = ["GPT-5.4\nClaude Sonnet 4.6"] if self.model_menu_open else []
            return _FakeLocator(texts=texts)
        return _FakeLocator()

    def inner_text(self, selector: str) -> str:
        if selector == "body":
            return self.body
        return ""

    def _open_more(self) -> None:
        self.more_open = True

    def _open_model_menu(self) -> None:
        self.model_menu_open = True

    def _set_prompt(self, value: str) -> None:
        self.prompt_value = value

    def _submit_prompt(self) -> None:
        self.response_ready = True
        self.body = f"{self.prompt_value}\nOK"


class _MenuItemRadioPage(_FakePage):
    def __init__(self) -> None:
        super().__init__()
        self.model_menu_open = True

    def evaluate(self, script: str) -> list[object] | bool:
        if "getBoundingClientRect()" in script:
            if "menuitemradio" not in script:
                return [
                    {
                        "tag": "div",
                        "role": "menuitemradio",
                        "aria_label": None,
                        "aria_selected": False,
                        "data_state": "checked",
                        "data_testid": None,
                        "class_list": ["menu-item", "selected-item"],
                        "text": "Claude Opus 4.7",
                        "outer_html": '<div role="menuitemradio">Claude Opus 4.7</div>',
                        "parent_tag": "div",
                        "bounding_box": {"x": 12, "y": 34, "width": 160, "height": 32},
                    }
                ]
            return [
                {
                    "tag": "div",
                    "role": "menuitemradio",
                    "aria_label": None,
                    "aria_selected": False,
                    "data_state": "unchecked",
                    "data_testid": None,
                    "class_list": ["menu-item", "best-item"],
                    "text": "Best",
                    "outer_html": '<div role="menuitemradio">Best</div>',
                    "parent_tag": "div",
                    "bounding_box": {"x": 12, "y": 34, "width": 160, "height": 32},
                },
                {
                    "tag": "div",
                    "role": "menuitemradio",
                    "aria_label": None,
                    "aria_selected": False,
                    "data_state": "unchecked",
                    "data_testid": None,
                    "class_list": ["menu-item", "sonar-item"],
                    "text": "Sonar",
                    "outer_html": '<div role="menuitemradio">Sonar</div>',
                    "parent_tag": "div",
                    "bounding_box": {"x": 12, "y": 70, "width": 160, "height": 32},
                },
                {
                    "tag": "div",
                    "role": "menuitemradio",
                    "aria_label": None,
                    "aria_selected": False,
                    "data_state": "unchecked",
                    "data_testid": None,
                    "class_list": ["menu-item", "gpt-item"],
                    "text": "GPT-5.4",
                    "outer_html": '<div role="menuitemradio">GPT-5.4</div>',
                    "parent_tag": "div",
                    "bounding_box": {"x": 12, "y": 106, "width": 160, "height": 32},
                },
                {
                    "tag": "div",
                    "role": "menuitemradio",
                    "aria_label": None,
                    "aria_selected": False,
                    "data_state": "unchecked",
                    "data_testid": None,
                    "class_list": ["menu-item", "claude-item"],
                    "text": "Claude Sonnet 4.6",
                    "outer_html": '<div role="menuitemradio">Claude Sonnet 4.6</div>',
                    "parent_tag": "div",
                    "bounding_box": {"x": 12, "y": 142, "width": 160, "height": 32},
                },
            ]
        return super().evaluate(script)


class _FakeKeyboard:
    def __init__(self) -> None:
        self.pressed: list[str] = []

    def press(self, value: str) -> None:
        self.pressed.append(value)


class _FakeContext:
    def __init__(self, page: _FakePage | None = None) -> None:
        self.page = page or _FakePage()
        self.pages = [self.page]
        self.closed = False

    def new_page(self) -> _FakePage:
        return self.page

    def close(self) -> None:
        self.closed = True


class _FakeChromium:
    def __init__(self, context: _FakeContext) -> None:
        self.context = context
        self.calls: list[dict[str, object]] = []

    def launch_persistent_context(self, profile_dir: str, *, channel: str, headless: bool, args: list[str]) -> _FakeContext:
        self.calls.append(
            {
                "profile_dir": profile_dir,
                "channel": channel,
                "headless": headless,
                "args": args,
            }
        )
        return self.context


class _FakePlaywright:
    def __init__(self, chromium: _FakeChromium) -> None:
        self.chromium = chromium


class _FakePlaywrightManager:
    def __init__(self, playwright: _FakePlaywright) -> None:
        self.playwright = playwright

    def __enter__(self) -> _FakePlaywright:
        return self.playwright

    def __exit__(self, exc_type: object, exc: object, tb: object) -> None:
        return None


class CapturePerplexityReconToolTests(unittest.TestCase):
    def _workspace_output_dir(self, name: str) -> str:
        output_dir = Path(__file__).resolve().parents[1] / "tmp" / "test-artifacts" / name
        output_dir.mkdir(parents=True, exist_ok=True)
        return str(output_dir)

    def test_resolve_output_dir_prefers_cli_then_env_then_default(self) -> None:
        with patch.dict("os.environ", {"GRACEKELLY_BROWSER_RECON_DIR": "D:\\Recon\\Env"}, clear=True):
            self.assertEqual(capture_perplexity_recon.resolve_output_dir("D:\\Recon\\Cli"), "D:\\Recon\\Cli")
            self.assertEqual(capture_perplexity_recon.resolve_output_dir(None), "D:\\Recon\\Env")

        with patch.dict("os.environ", {}, clear=True):
            resolved = capture_perplexity_recon.resolve_output_dir(None, today=date(2026, 3, 18))
        self.assertTrue(resolved.endswith(str(Path("tmp", "browser-recon", "2026-03-18"))))

    def test_capture_recon_collects_home_more_and_model_menu_artifacts(self) -> None:
        context = _FakeContext()
        chromium = _FakeChromium(context)
        manager = _FakePlaywrightManager(_FakePlaywright(chromium))
        printed: list[str] = []

        temp_dir = self._workspace_output_dir("auto")
        manifest = capture_perplexity_recon.capture_recon(
            profile_dir=r"D:\GraceKelly\tmp\browser-recon\perplexity-profile",
            output_dir=temp_dir,
            base_url="https://www.perplexity.ai",
            channel="chrome",
            interactive_pause=False,
            sync_playwright_factory=lambda: manager,
            print_func=printed.append,
        )

        files = manifest["files"]
        self.assertTrue((Path(temp_dir) / files["home_screenshot"]).exists())
        self.assertTrue((Path(temp_dir) / files["home_buttons"]).exists())
        self.assertTrue((Path(temp_dir) / files["composer_html"]).exists())
        self.assertTrue((Path(temp_dir) / files["more_screenshot"]).exists())
        self.assertTrue((Path(temp_dir) / files["more_buttons"]).exists())
        self.assertTrue((Path(temp_dir) / files["model_picker_screenshot"]).exists())
        self.assertTrue((Path(temp_dir) / files["model_menu_snapshot"]).exists())
        menu_payload = json.loads((Path(temp_dir) / files["model_menu_snapshot"]).read_text(encoding="utf-8"))
        self.assertIn("GPT-5.4", menu_payload)
        self.assertTrue(manifest["more_clicked"])
        self.assertTrue(manifest["model_button_visible_after_more"])

        self.assertEqual(chromium.calls[0]["channel"], "chrome")
        self.assertFalse(chromium.calls[0]["headless"])
        self.assertTrue(context.closed)

    def test_capture_recon_collects_model_menu_attrs_snapshot(self) -> None:
        context = _FakeContext()
        chromium = _FakeChromium(context)
        manager = _FakePlaywrightManager(_FakePlaywright(chromium))

        temp_dir = self._workspace_output_dir("menu-attrs")
        manifest = capture_perplexity_recon.capture_recon(
            profile_dir=r"D:\GraceKelly\tmp\browser-recon\perplexity-profile",
            output_dir=temp_dir,
            base_url="https://www.perplexity.ai",
            channel="chrome",
            interactive_pause=False,
            sync_playwright_factory=lambda: manager,
        )

        attrs_path = Path(temp_dir) / manifest["files"]["model_menu_attrs_snapshot"]
        self.assertTrue(attrs_path.exists())
        payload = json.loads(attrs_path.read_text(encoding="utf-8"))
        self.assertEqual(
            payload,
            [
                {
                    "tag": "button",
                    "role": "menuitem",
                    "aria_label": "Best",
                    "aria_selected": None,
                    "data_state": None,
                    "data_testid": None,
                    "class_list": ["menu-item", "best-item"],
                    "text": "Best",
                    "outer_html": '<button aria-label="Best">Best</button>',
                    "parent_tag": "div",
                    "bounding_box": {"x": 12, "y": 34, "width": 160, "height": 32},
                },
                {
                    "tag": "button",
                    "role": "menuitem",
                    "aria_label": "Sonar",
                    "aria_selected": False,
                    "data_state": "inactive",
                    "data_testid": "sonar-option",
                    "class_list": ["menu-item", "sonar-item"],
                    "text": "Sonar",
                    "outer_html": '<button aria-label="Sonar">Sonar</button>',
                    "parent_tag": "div",
                    "bounding_box": {"x": 12, "y": 70, "width": 160, "height": 32},
                },
                {
                    "tag": "button",
                    "role": "menuitem",
                    "aria_label": "Claude Sonnet 4.6",
                    "aria_selected": False,
                    "data_state": "inactive",
                    "data_testid": "claude-sonnet-option",
                    "class_list": ["menu-item", "claude-item"],
                    "text": "Claude Sonnet 4.6",
                    "outer_html": '<button aria-label="Claude Sonnet 4.6">Claude Sonnet 4.6</button>',
                    "parent_tag": "div",
                    "bounding_box": {"x": 12, "y": 106, "width": 160, "height": 32},
                },
            ],
        )

    def test_capture_recon_can_pause_for_manual_capture(self) -> None:
        context = _FakeContext()
        chromium = _FakeChromium(context)
        manager = _FakePlaywrightManager(_FakePlaywright(chromium))
        prompts: list[str] = []

        temp_dir = self._workspace_output_dir("manual")

        def _input_func(prompt: str) -> str:
            prompts.append(prompt)
            return ""

        manifest = capture_perplexity_recon.capture_recon(
            profile_dir=r"D:\GraceKelly\tmp\browser-recon\perplexity-profile",
            output_dir=temp_dir,
            base_url="https://www.perplexity.ai",
            channel="chrome",
            interactive_pause=True,
            sync_playwright_factory=lambda: manager,
            input_func=_input_func,
        )

        self.assertEqual(len(prompts), 1)
        self.assertIn("manual_screenshot", manifest["files"])
        self.assertTrue((Path(temp_dir) / manifest["files"]["manual_screenshot"]).exists())

    def test_capture_recon_can_collect_post_response_artifacts(self) -> None:
        context = _FakeContext()
        chromium = _FakeChromium(context)
        manager = _FakePlaywrightManager(_FakePlaywright(chromium))

        temp_dir = self._workspace_output_dir("response")
        manifest = capture_perplexity_recon.capture_recon(
            profile_dir=r"D:\GraceKelly\tmp\browser-recon\perplexity-profile",
            output_dir=temp_dir,
            base_url="https://www.perplexity.ai",
            channel="chrome",
            prompt="Reply with only OK",
            timeout_seconds=30,
            interactive_pause=False,
            sync_playwright_factory=lambda: manager,
        )

        self.assertTrue(manifest["prompt_submitted"])
        self.assertEqual(manifest["response_source"], 'main [data-message-author-role="assistant"]')
        self.assertFalse(manifest["response_used_body_fallback"])
        self.assertTrue((Path(temp_dir) / manifest["files"]["response_screenshot"]).exists())
        self.assertTrue((Path(temp_dir) / manifest["files"]["response_main_html"]).exists())
        payload = json.loads((Path(temp_dir) / manifest["files"]["response_candidates"]).read_text(encoding="utf-8"))
        self.assertEqual(payload["selected_text"], "OK")
        self.assertEqual(payload["response_source"], 'main [data-message-author-role="assistant"]')

    def test_model_menu_attributes_snapshot_includes_menuitemradio_entries(self) -> None:
        payload = capture_perplexity_recon._model_menu_attributes_snapshot(
            _MenuItemRadioPage(),
            selectors=PerplexitySelectors(),
        )

        self.assertEqual(
            [entry["text"] for entry in payload],
            ["Best", "Sonar", "GPT-5.4", "Claude Sonnet 4.6"],
        )

    def test_main_returns_error_when_capture_fails(self) -> None:
        with (
            patch.object(
                capture_perplexity_recon,
                "parse_args",
                return_value=argparse.Namespace(
                    profile_dir="D:\\Profiles\\Broken",
                    output_dir="D:\\Recon\\Broken",
                    base_url="https://www.perplexity.ai",
                    channel="chrome",
                    interactive_pause=False,
                    prompt=None,
                    timeout_seconds=60,
                ),
            ),
            patch.object(capture_perplexity_recon, "capture_recon", side_effect=RuntimeError("broken")),
            patch("builtins.print") as print_mock,
        ):
            code = capture_perplexity_recon.main()

        self.assertEqual(code, 2)
        self.assertIn("Failed to capture Perplexity DOM recon", print_mock.call_args.args[0])

    def test_main_returns_ok_when_capture_succeeds(self) -> None:
        with (
            patch.object(
                capture_perplexity_recon,
                "parse_args",
                return_value=argparse.Namespace(
                    profile_dir=None,
                    output_dir=None,
                    base_url="https://www.perplexity.ai",
                    channel="chrome",
                    interactive_pause=True,
                    prompt=None,
                    timeout_seconds=60,
                ),
            ),
            patch.object(capture_perplexity_recon, "resolve_output_dir", return_value="D:\\Recon\\Today"),
            patch.object(capture_perplexity_recon, "resolve_profile_dir", return_value="D:\\Profiles\\Perplexity"),
            patch.object(capture_perplexity_recon, "capture_recon"),
            patch("builtins.print") as print_mock,
        ):
            code = capture_perplexity_recon.main()

        self.assertEqual(code, 0)
        self.assertEqual(print_mock.call_args.args[0], "Perplexity DOM recon is ready at D:\\Recon\\Today")


class LocatorIsVisibleTests(unittest.TestCase):
    def test_visible_locator_returns_true(self) -> None:
        locator = _FakeLocator(visible=True)
        self.assertTrue(capture_perplexity_recon._locator_is_visible(locator))

    def test_invisible_locator_returns_false(self) -> None:
        locator = _FakeLocator(visible=False)
        self.assertFalse(capture_perplexity_recon._locator_is_visible(locator))

    def test_locator_without_is_visible_falls_back_to_count(self) -> None:
        class _CountLocator:
            first = None

            def count(self) -> int:
                return 1

        locator = _CountLocator()
        locator.first = locator  # type: ignore[assignment]
        self.assertTrue(capture_perplexity_recon._locator_is_visible(locator))

    def test_locator_is_visible_raises_returns_false(self) -> None:
        class _RaisingLocator:
            first = None

            def is_visible(self) -> bool:
                raise RuntimeError("not connected")

        locator = _RaisingLocator()
        locator.first = locator  # type: ignore[assignment]
        self.assertFalse(capture_perplexity_recon._locator_is_visible(locator))

    def test_locator_with_no_methods_returns_false(self) -> None:
        class _BareLoc:
            first = None
        locator = _BareLoc()
        locator.first = locator  # type: ignore[assignment]
        self.assertFalse(capture_perplexity_recon._locator_is_visible(locator))


class LocatorExistsTests(unittest.TestCase):
    def test_count_positive_returns_true(self) -> None:
        locator = _FakeLocator(visible=True)
        self.assertTrue(capture_perplexity_recon._locator_exists(locator))

    def test_count_zero_returns_false(self) -> None:
        locator = _FakeLocator(visible=False)
        self.assertFalse(capture_perplexity_recon._locator_exists(locator))

    def test_count_raises_returns_false(self) -> None:
        class _RaisingCount:
            first = None

            def count(self) -> int:
                raise RuntimeError("boom")

        locator = _RaisingCount()
        locator.first = locator  # type: ignore[assignment]
        self.assertFalse(capture_perplexity_recon._locator_exists(locator))


class BodyTextTests(unittest.TestCase):
    def test_returns_inner_text_from_body(self) -> None:
        class _FakePage:
            def inner_text(self, selector: str) -> str:
                return "page content"

        self.assertEqual(capture_perplexity_recon._body_text(_FakePage()), "page content")

    def test_returns_empty_string_on_exception(self) -> None:
        class _FailingPage:
            def inner_text(self, selector: str) -> str:
                raise RuntimeError("not loaded")

        self.assertEqual(capture_perplexity_recon._body_text(_FailingPage()), "")


class WriteJsonTests(unittest.TestCase):
    def test_writes_valid_json(self) -> None:
        path = _TMP_ROOT / "write-json-valid.json"
        path.unlink(missing_ok=True)
        try:
            capture_perplexity_recon._write_json(path, {"key": "value", "num": 42})
            loaded = json.loads(path.read_text(encoding="utf-8"))
            self.assertEqual(loaded["key"], "value")
            self.assertEqual(loaded["num"], 42)
        finally:
            path.unlink(missing_ok=True)

    def test_writes_unicode_content(self) -> None:
        path = _TMP_ROOT / "write-json-unicode.json"
        path.unlink(missing_ok=True)
        try:
            capture_perplexity_recon._write_json(path, {"text": "\u042e\u043d\u0438\u043a\u043e\u0434 \U0001f30d"})
            content = path.read_text(encoding="utf-8")
            self.assertIn("\u042e\u043d\u0438\u043a\u043e\u0434", content)
        finally:
            path.unlink(missing_ok=True)


if __name__ == "__main__":
    unittest.main()
