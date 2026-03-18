from __future__ import annotations

import argparse
from datetime import date
import json
from pathlib import Path
import unittest
from unittest.mock import patch

from gracekelly.tools import capture_perplexity_recon


class _FakeLocator:
    def __init__(self, *, visible: bool = False, click=None, inner_html: str = "", texts: list[str] | None = None) -> None:
        self._visible = visible
        self._click = click
        self._inner_html = inner_html
        self._texts = texts or []
        self.first = self

    def is_visible(self) -> bool:
        return self._visible

    def count(self) -> int:
        return 1 if self._visible or self._inner_html or self._texts else 0

    def click(self) -> None:
        if self._click is not None:
            self._click()

    def inner_html(self) -> str:
        return self._inner_html

    def all_inner_texts(self) -> list[str]:
        return list(self._texts)


class _FakePage:
    def __init__(self) -> None:
        self.goto_calls: list[tuple[str, str]] = []
        self.screenshot_paths: list[str] = []
        self.more_open = False
        self.model_menu_open = False
        self.body = "Type @ for connectors and sources\nType / for search modes"
        self.composer_html = "<div>composer</div>"

    def goto(self, url: str, wait_until: str) -> None:
        self.goto_calls.append((url, wait_until))

    def screenshot(self, *, path: str, full_page: bool) -> None:
        Path(path).write_text(f"screenshot:{full_page}", encoding="utf-8")
        self.screenshot_paths.append(path)

    def evaluate(self, script: str):
        if "querySelectorAll('button')" in script:
            if self.more_open:
                return ["More::More", "Model::Model", "Submit::Submit"]
            return ["New Thread", "More::More", "Submit::Submit"]
        raise AssertionError(f"Unexpected script: {script}")

    def locator(self, selector: str) -> _FakeLocator:
        if selector == 'div#ask-input[role="textbox"][contenteditable="true"]':
            return _FakeLocator(visible=True)
        if selector == "form":
            return _FakeLocator(visible=True, inner_html=self.composer_html)
        if 'aria-label="Model"' in selector:
            return _FakeLocator(visible=self.more_open, click=self._open_model_menu)
        if selector == 'button[aria-label="More"]':
            return _FakeLocator(visible=True, click=self._open_more)
        if selector == 'button:has-text("More")':
            return _FakeLocator(visible=True, click=self._open_more)
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

    def __exit__(self, exc_type, exc, tb) -> None:
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
        self.assertTrue(resolved.endswith("tmp\\browser-recon\\2026-03-18"))

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

    def test_capture_recon_can_pause_for_manual_capture(self) -> None:
        context = _FakeContext()
        chromium = _FakeChromium(context)
        manager = _FakePlaywrightManager(_FakePlaywright(chromium))
        prompts: list[str] = []

        temp_dir = self._workspace_output_dir("manual")
        manifest = capture_perplexity_recon.capture_recon(
            profile_dir=r"D:\GraceKelly\tmp\browser-recon\perplexity-profile",
            output_dir=temp_dir,
            base_url="https://www.perplexity.ai",
            channel="chrome",
            interactive_pause=True,
            sync_playwright_factory=lambda: manager,
            input_func=lambda prompt: prompts.append(prompt) or "",
        )

        self.assertEqual(len(prompts), 1)
        self.assertIn("manual_screenshot", manifest["files"])
        self.assertTrue((Path(temp_dir) / manifest["files"]["manual_screenshot"]).exists())

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


if __name__ == "__main__":
    unittest.main()
