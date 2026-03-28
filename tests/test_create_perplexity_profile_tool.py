from __future__ import annotations

import argparse
import unittest
from unittest.mock import patch

from gracekelly.tools import create_perplexity_profile


class _FakePage:
    def __init__(self) -> None:
        self.goto_calls: list[tuple[str, str]] = []

    def goto(self, url: str, wait_until: str) -> None:
        self.goto_calls.append((url, wait_until))


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


class CreatePerplexityProfileToolTests(unittest.TestCase):
    def test_resolve_profile_dir_prefers_cli_then_env_then_default(self) -> None:
        with patch.dict("os.environ", {"GRACEKELLY_BROWSER_PROFILE_DIR": "D:\\Profiles\\Env"}, clear=True):
            self.assertEqual(create_perplexity_profile.resolve_profile_dir("D:\\Profiles\\Cli"), "D:\\Profiles\\Cli")
            self.assertEqual(create_perplexity_profile.resolve_profile_dir(None), "D:\\Profiles\\Env")

        with patch.dict("os.environ", {}, clear=True):
            self.assertEqual(create_perplexity_profile.resolve_profile_dir(None), create_perplexity_profile.DEFAULT_PROFILE_DIR)

    def test_create_profile_launches_persistent_context_and_waits_for_input(self) -> None:
        context = _FakeContext()
        chromium = _FakeChromium(context)
        manager = _FakePlaywrightManager(_FakePlaywright(chromium))
        prompts: list[str] = []
        printed: list[str] = []
        profile_dir = r"D:\GraceKelly\tmp\browser-recon\perplexity-profile-test"
        with patch("pathlib.Path.mkdir") as mkdir_mock:
            create_perplexity_profile.create_profile(
                profile_dir=profile_dir,
                base_url="https://www.perplexity.ai",
                channel="chrome",
                sync_playwright_factory=lambda: manager,
                input_func=lambda prompt: prompts.append(prompt) or "",
                print_func=printed.append,
            )

        mkdir_mock.assert_called_once()
        self.assertEqual(chromium.calls[0]["profile_dir"], profile_dir)
        self.assertEqual(chromium.calls[0]["channel"], "chrome")
        self.assertFalse(chromium.calls[0]["headless"])
        self.assertEqual(context.page.goto_calls, [("https://www.perplexity.ai", "domcontentloaded")])
        self.assertEqual(len(prompts), 1)
        self.assertTrue(context.closed)

    def test_main_returns_error_when_creation_fails(self) -> None:
        with (
            patch.object(
                create_perplexity_profile,
                "parse_args",
                return_value=argparse.Namespace(profile_dir="D:\\Profiles\\Broken", base_url="https://www.perplexity.ai", channel="chrome"),
            ),
            patch.object(create_perplexity_profile, "create_profile", side_effect=RuntimeError("broken")),
            patch("builtins.print") as print_mock,
        ):
            code = create_perplexity_profile.main()

        self.assertEqual(code, 2)
        self.assertIn("Failed to create Perplexity profile", print_mock.call_args.args[0])

    def test_main_returns_ok_when_creation_succeeds(self) -> None:
        with (
            patch.object(
                create_perplexity_profile,
                "parse_args",
                return_value=argparse.Namespace(profile_dir=None, base_url="https://www.perplexity.ai", channel="chrome"),
            ),
            patch.object(create_perplexity_profile, "resolve_profile_dir", return_value="D:\\Profiles\\Perplexity"),
            patch.object(create_perplexity_profile, "create_profile"),
            patch("builtins.print") as print_mock,
        ):
            code = create_perplexity_profile.main()

        self.assertEqual(code, 0)
        self.assertEqual(print_mock.call_args.args[0], "Perplexity profile is ready at D:\\Profiles\\Perplexity")

    def test_create_profile_uses_new_page_when_pages_is_empty(self) -> None:
        context = _FakeContext()
        context.pages = []  # force new_page() path
        chromium = _FakeChromium(context)
        manager = _FakePlaywrightManager(_FakePlaywright(chromium))
        with patch("pathlib.Path.mkdir"):
            create_perplexity_profile.create_profile(
                profile_dir=r"D:\tmp\profile",
                base_url="https://www.perplexity.ai",
                channel="chrome",
                sync_playwright_factory=lambda: manager,
                input_func=lambda _: "",
                print_func=lambda _: None,
            )
        self.assertEqual(context.page.goto_calls, [("https://www.perplexity.ai", "domcontentloaded")])

    def test_create_profile_closes_context_even_on_exception(self) -> None:
        context = _FakeContext()
        chromium = _FakeChromium(context)
        manager = _FakePlaywrightManager(_FakePlaywright(chromium))

        def _raise(_: str) -> str:
            raise RuntimeError("input interrupted")

        with patch("pathlib.Path.mkdir"):
            with self.assertRaises(RuntimeError):
                create_perplexity_profile.create_profile(
                    profile_dir=r"D:\tmp\profile",
                    base_url="https://www.perplexity.ai",
                    channel="chrome",
                    sync_playwright_factory=lambda: manager,
                    input_func=_raise,
                    print_func=lambda _: None,
                )
        self.assertTrue(context.closed)


if __name__ == "__main__":
    unittest.main()
