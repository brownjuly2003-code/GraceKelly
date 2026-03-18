from __future__ import annotations

import os
import unittest
from unittest.mock import patch

from gracekelly.config import Settings


class SettingsTests(unittest.TestCase):
    def test_from_env_uses_default_postgres_connect_timeout(self) -> None:
        with patch.dict(os.environ, {}, clear=True):
            settings = Settings.from_env()

        self.assertEqual(settings.postgres_connect_timeout_seconds, 5)
        self.assertEqual(settings.openai_base_url, "https://api.openai.com/v1")
        self.assertEqual(settings.openai_timeout_seconds, 60.0)
        self.assertEqual(settings.browser_playwright_channel, "chrome")
        self.assertFalse(settings.browser_playwright_headless)
        self.assertTrue(settings.browser_circuit_breaker_enabled)
        self.assertEqual(settings.browser_circuit_breaker_failure_threshold, 3)
        self.assertEqual(settings.browser_circuit_breaker_cooldown_seconds, 60)

    def test_from_env_reads_postgres_connect_timeout(self) -> None:
        with patch.dict(
            os.environ,
            {
                "GRACEKELLY_POSTGRES_CONNECT_TIMEOUT_SECONDS": "9",
                "GRACEKELLY_STORAGE_BACKEND": "postgres",
                "GRACEKELLY_POSTGRES_DSN": "postgresql://example",
            },
            clear=True,
        ):
            settings = Settings.from_env()

        self.assertEqual(settings.storage_backend, "postgres")
        self.assertEqual(settings.postgres_dsn, "postgresql://example")
        self.assertEqual(settings.postgres_connect_timeout_seconds, 9)

    def test_from_env_reads_openai_compat_settings(self) -> None:
        with patch.dict(
            os.environ,
            {
                "GRACEKELLY_OPENAI_API_KEY": "test-key",
                "GRACEKELLY_OPENAI_BASE_URL": "https://example.test/v1",
                "GRACEKELLY_OPENAI_TIMEOUT_SECONDS": "45",
            },
            clear=True,
        ):
            settings = Settings.from_env()

        self.assertEqual(settings.openai_api_key, "test-key")
        self.assertEqual(settings.openai_base_url, "https://example.test/v1")
        self.assertEqual(settings.openai_timeout_seconds, 45.0)

    def test_from_env_reads_playwright_browser_settings(self) -> None:
        with patch.dict(
            os.environ,
            {
                "GRACEKELLY_BROWSER_AUTOMATION_BACKEND": "playwright",
                "GRACEKELLY_BROWSER_PLAYWRIGHT_CHANNEL": "msedge",
                "GRACEKELLY_BROWSER_PLAYWRIGHT_HEADLESS": "true",
                "GRACEKELLY_BROWSER_CIRCUIT_BREAKER_ENABLED": "false",
                "GRACEKELLY_BROWSER_CIRCUIT_BREAKER_FAILURE_THRESHOLD": "5",
                "GRACEKELLY_BROWSER_CIRCUIT_BREAKER_COOLDOWN_SECONDS": "120",
            },
            clear=True,
        ):
            settings = Settings.from_env()

        self.assertEqual(settings.browser_automation_backend, "playwright")
        self.assertEqual(settings.browser_playwright_channel, "msedge")
        self.assertTrue(settings.browser_playwright_headless)
        self.assertFalse(settings.browser_circuit_breaker_enabled)
        self.assertEqual(settings.browser_circuit_breaker_failure_threshold, 5)
        self.assertEqual(settings.browser_circuit_breaker_cooldown_seconds, 120)
