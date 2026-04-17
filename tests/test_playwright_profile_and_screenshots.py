from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from typing import Any

from gracekelly.adapters.browser.automation import BrowserProfileBusyError
from gracekelly.adapters.browser.playwright_driver import (
    PlaywrightBrowserAutomation,
    PlaywrightBrowserRuntimeConfig,
    _profile_is_locked,
)
from gracekelly.adapters.browser.session import BrowserSessionConfig, BrowserSessionManager


class ProfileLockDetectionTests(unittest.TestCase):
    def test_missing_profile_dir_returns_none(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            missing = Path(temp) / "nope"
            self.assertIsNone(_profile_is_locked(str(missing)))

    def test_clean_profile_returns_none(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            self.assertIsNone(_profile_is_locked(temp))

    def test_singleton_lock_is_detected(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            lock = Path(temp) / "SingletonLock"
            lock.write_text("")
            result = _profile_is_locked(temp)
            self.assertIsNotNone(result)
            assert result is not None
            self.assertTrue(result.endswith("SingletonLock"))

    def test_singleton_socket_is_detected(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            (Path(temp) / "SingletonSocket").write_text("")
            result = _profile_is_locked(temp)
            self.assertIsNotNone(result)


class _RecordingPage:
    def __init__(self) -> None:
        self.screenshot_calls: list[dict[str, Any]] = []

    def screenshot(self, **kwargs: Any) -> None:
        self.screenshot_calls.append(kwargs)
        path = kwargs.get("path")
        if path is not None:
            Path(path).write_bytes(b"PNG")


class ScreenshotHelperTests(unittest.TestCase):
    def _make_automation(self, screenshots_dir: str | None) -> PlaywrightBrowserAutomation:
        automation = PlaywrightBrowserAutomation(
            runtime=PlaywrightBrowserRuntimeConfig(screenshots_dir=screenshots_dir),
            sync_playwright_factory=lambda: None,
        )
        return automation

    def test_screenshot_disabled_returns_none(self) -> None:
        automation = self._make_automation(screenshots_dir=None)
        automation._page = _RecordingPage()
        self.assertIsNone(automation._screenshot("test"))

    def test_screenshot_without_page_returns_none(self) -> None:
        with tempfile.TemporaryDirectory() as dest:
            automation = self._make_automation(screenshots_dir=dest)
            self.assertIsNone(automation._screenshot("test"))

    def test_screenshot_saves_file_and_returns_path(self) -> None:
        with tempfile.TemporaryDirectory() as dest:
            automation = self._make_automation(screenshots_dir=dest)
            page = _RecordingPage()
            automation._page = page
            saved = automation._screenshot("01-session-ready")
            self.assertIsNotNone(saved)
            assert saved is not None
            saved_path = Path(saved)
            self.assertTrue(saved_path.exists())
            self.assertTrue(saved_path.name.endswith("01-session-ready.png"))
            self.assertEqual(len(page.screenshot_calls), 1)
            self.assertTrue(page.screenshot_calls[0].get("full_page"))

    def test_screenshot_sanitizes_step_name(self) -> None:
        with tempfile.TemporaryDirectory() as dest:
            automation = self._make_automation(screenshots_dir=dest)
            automation._page = _RecordingPage()
            saved = automation._screenshot("bad name/with:weird*chars")
            self.assertIsNotNone(saved)
            assert saved is not None
            name = Path(saved).name
            # no slashes, colons, or asterisks in the filename
            self.assertNotRegex(name, r"[\\/:*]")

    def test_screenshot_failure_returns_none_without_raising(self) -> None:
        class _FailingPage:
            def screenshot(self, **kwargs: Any) -> None:
                raise RuntimeError("fake playwright failure")

        with tempfile.TemporaryDirectory() as dest:
            automation = self._make_automation(screenshots_dir=dest)
            automation._page = _FailingPage()
            self.assertIsNone(automation._screenshot("oops"))


class EnsureSessionPreflightTests(unittest.TestCase):
    def test_ensure_session_rejects_locked_profile(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            (Path(temp) / "SingletonLock").write_text("")
            session = BrowserSessionManager(
                BrowserSessionConfig(
                    enabled=True,
                    provider="perplexity",
                    base_url="https://www.perplexity.ai",
                    profile_dir=temp,
                )
            )
            automation = PlaywrightBrowserAutomation(
                sync_playwright_factory=lambda: None,
            )
            with self.assertRaises(BrowserProfileBusyError) as ctx:
                automation.ensure_session(session)
            self.assertIn("SingletonLock", str(ctx.exception))


if __name__ == "__main__":
    unittest.main()
