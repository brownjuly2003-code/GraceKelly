from __future__ import annotations

import unittest

from gracekelly.adapters.browser.session import BrowserSessionConfig, BrowserSessionManager


class BrowserSessionManagerTests(unittest.TestCase):
    def _config(
        self,
        *,
        enabled: bool = True,
        provider: str = "perplexity",
        base_url: str = "https://www.perplexity.ai",
        profile_dir: str | None = "/tmp/test-profile",
    ) -> BrowserSessionConfig:
        return BrowserSessionConfig(
            enabled=enabled,
            provider=provider,
            base_url=base_url,
            profile_dir=profile_dir,
        )

    def test_configured_when_enabled_with_profile(self) -> None:
        mgr = BrowserSessionManager(self._config())
        self.assertTrue(mgr.state.configured)

    def test_not_configured_when_disabled(self) -> None:
        mgr = BrowserSessionManager(self._config(enabled=False))
        self.assertFalse(mgr.state.configured)

    def test_not_configured_without_profile_dir(self) -> None:
        mgr = BrowserSessionManager(self._config(profile_dir=None))
        self.assertFalse(mgr.state.configured)

    def test_mark_active(self) -> None:
        mgr = BrowserSessionManager(self._config())
        mgr.mark_active()
        self.assertTrue(mgr.state.active)
        self.assertIsNone(mgr.state.last_error)

    def test_mark_error(self) -> None:
        mgr = BrowserSessionManager(self._config())
        mgr.mark_active()
        mgr.mark_error("something broke")
        self.assertFalse(mgr.state.active)
        self.assertEqual(mgr.state.last_error, "something broke")

    def test_mark_idle(self) -> None:
        mgr = BrowserSessionManager(self._config())
        mgr.mark_active()
        mgr.mark_idle()
        self.assertFalse(mgr.state.active)
        self.assertIsNone(mgr.state.last_error)

    def test_is_ready_requires_configured_and_active(self) -> None:
        mgr = BrowserSessionManager(self._config())
        self.assertFalse(mgr.is_ready())
        mgr.mark_active()
        self.assertTrue(mgr.is_ready())

    def test_healthcheck_ok(self) -> None:
        mgr = BrowserSessionManager(self._config())
        health = mgr.healthcheck()
        self.assertEqual(health["status"], "ok")

    def test_healthcheck_ok_when_idle_without_error(self) -> None:
        mgr = BrowserSessionManager(self._config())
        mgr.mark_active()
        mgr.mark_idle()
        health = mgr.healthcheck()
        self.assertEqual(health["status"], "ok")

    def test_healthcheck_degraded_when_unconfigured(self) -> None:
        mgr = BrowserSessionManager(self._config(profile_dir=None))
        health = mgr.healthcheck()
        self.assertEqual(health["status"], "degraded")

    def test_healthcheck_degraded_after_error(self) -> None:
        mgr = BrowserSessionManager(self._config())
        mgr.mark_error("something broke")
        health = mgr.healthcheck()
        self.assertEqual(health["status"], "degraded")

    def test_state_returns_copy(self) -> None:
        mgr = BrowserSessionManager(self._config())
        state1 = mgr.state
        mgr.mark_active()
        state2 = mgr.state
        self.assertFalse(state1.active)
        self.assertTrue(state2.active)

    def test_profile_dir_traversal_rejected(self) -> None:
        with self.assertRaises(ValueError) as ctx:
            BrowserSessionManager(self._config(profile_dir="/tmp/../etc/passwd"))
        self.assertIn("disallowed", str(ctx.exception))

    def test_profile_dir_tilde_rejected(self) -> None:
        with self.assertRaises(ValueError) as ctx:
            BrowserSessionManager(self._config(profile_dir="~/profiles/test"))
        self.assertIn("disallowed", str(ctx.exception))

    def test_valid_absolute_profile_dir_accepted(self) -> None:
        mgr = BrowserSessionManager(self._config(profile_dir="/opt/gracekelly/profiles/main"))
        self.assertEqual(mgr.state.profile_dir, "/opt/gracekelly/profiles/main")
