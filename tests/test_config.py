from __future__ import annotations

import os
import unittest
from unittest.mock import patch

from gracekelly.config import Settings, _env_float, _env_int


class SettingsTests(unittest.TestCase):
    def test_from_env_uses_default_postgres_connect_timeout(self) -> None:
        with patch.dict(os.environ, {}, clear=True):
            settings = Settings.from_env()

        self.assertEqual(settings.postgres_connect_timeout_seconds, 5)
        self.assertEqual(settings.openai_base_url, "https://api.openai.com/v1")
        self.assertEqual(settings.openai_timeout_seconds, 60.0)
        self.assertEqual(settings.browser_call_timeout_seconds, 120)
        self.assertEqual(settings.browser_human_action_delay_seconds, 1.0)
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
                "GRACEKELLY_BROWSER_CALL_TIMEOUT_SECONDS": "180",
                "GRACEKELLY_BROWSER_HUMAN_ACTION_DELAY_SECONDS": "1.75",
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
        self.assertEqual(settings.browser_call_timeout_seconds, 180)
        self.assertEqual(settings.browser_human_action_delay_seconds, 1.75)
        self.assertFalse(settings.browser_circuit_breaker_enabled)
        self.assertEqual(settings.browser_circuit_breaker_failure_threshold, 5)
        self.assertEqual(settings.browser_circuit_breaker_cooldown_seconds, 120)

    def test_invalid_browser_call_timeout_env_falls_back_to_default_and_logs_warning(self) -> None:
        with patch.dict(os.environ, {"GRACEKELLY_BROWSER_CALL_TIMEOUT_SECONDS": "abc"}, clear=True):
            with self.assertLogs("gracekelly.config", level="WARNING") as captured:
                settings = Settings.from_env()

        self.assertEqual(settings.browser_call_timeout_seconds, 120)
        self.assertEqual(len(captured.output), 1)
        self.assertIn("GRACEKELLY_BROWSER_CALL_TIMEOUT_SECONDS", captured.output[0])

    def test_invalid_int_env_falls_back_to_default(self) -> None:
        with patch.dict(os.environ, {"GRACEKELLY_PORT": "not_a_number"}, clear=True):
            settings = Settings.from_env()
        self.assertEqual(settings.port, 8011)

    def test_invalid_float_env_falls_back_to_default(self) -> None:
        with patch.dict(os.environ, {"GRACEKELLY_MISTRAL_TIMEOUT_SECONDS": "abc"}, clear=True):
            settings = Settings.from_env()
        self.assertEqual(settings.mistral_timeout_seconds, 30.0)

    def test_env_int_valid(self) -> None:
        with patch.dict(os.environ, {"TEST_INT": "42"}, clear=False):
            self.assertEqual(_env_int("TEST_INT", "0"), 42)

    def test_env_int_invalid(self) -> None:
        with patch.dict(os.environ, {"TEST_INT": "bad"}, clear=False):
            self.assertEqual(_env_int("TEST_INT", "7"), 7)

    def test_env_float_valid(self) -> None:
        with patch.dict(os.environ, {"TEST_FLOAT": "3.14"}, clear=False):
            self.assertAlmostEqual(_env_float("TEST_FLOAT", "0"), 3.14)

    def test_env_float_invalid(self) -> None:
        with patch.dict(os.environ, {"TEST_FLOAT": "bad"}, clear=False):
            self.assertAlmostEqual(_env_float("TEST_FLOAT", "1.5"), 1.5)
