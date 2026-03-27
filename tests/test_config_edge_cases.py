from __future__ import annotations

import os
import unittest
from unittest.mock import patch

from gracekelly.config import Settings


class SettingsRateLimitTests(unittest.TestCase):
    def test_rate_limit_zero_becomes_none(self) -> None:
        """GRACEKELLY_RATE_LIMIT_PER_MINUTE=0 must resolve to None."""
        with patch.dict(os.environ, {"GRACEKELLY_RATE_LIMIT_PER_MINUTE": "0"}, clear=True):
            s = Settings.from_env()
        self.assertIsNone(s.rate_limit_per_minute)

    def test_rate_limit_positive_preserved(self) -> None:
        with patch.dict(os.environ, {"GRACEKELLY_RATE_LIMIT_PER_MINUTE": "60"}, clear=True):
            s = Settings.from_env()
        self.assertEqual(s.rate_limit_per_minute, 60)

    def test_rate_limit_default_is_none(self) -> None:
        with patch.dict(os.environ, {}, clear=True):
            s = Settings.from_env()
        self.assertIsNone(s.rate_limit_per_minute)


class SettingsBooleanFlagsTests(unittest.TestCase):
    def test_browser_enabled_true(self) -> None:
        with patch.dict(os.environ, {"GRACEKELLY_BROWSER_ENABLED": "true"}, clear=True):
            s = Settings.from_env()
        self.assertTrue(s.browser_enabled)

    def test_browser_enabled_false_by_default(self) -> None:
        with patch.dict(os.environ, {}, clear=True):
            s = Settings.from_env()
        self.assertFalse(s.browser_enabled)

    def test_postgres_pool_enabled_true(self) -> None:
        with patch.dict(os.environ, {"GRACEKELLY_POSTGRES_POOL_ENABLED": "true"}, clear=True):
            s = Settings.from_env()
        self.assertTrue(s.postgres_pool_enabled)

    def test_postgres_pool_enabled_false_by_default(self) -> None:
        with patch.dict(os.environ, {}, clear=True):
            s = Settings.from_env()
        self.assertFalse(s.postgres_pool_enabled)

    def test_browser_scripted_logged_in_default_true(self) -> None:
        with patch.dict(os.environ, {}, clear=True):
            s = Settings.from_env()
        self.assertTrue(s.browser_scripted_logged_in)

    def test_browser_scripted_logged_in_false(self) -> None:
        with patch.dict(
            os.environ, {"GRACEKELLY_BROWSER_SCRIPTED_LOGGED_IN": "false"}, clear=True
        ):
            s = Settings.from_env()
        self.assertFalse(s.browser_scripted_logged_in)


class SettingsPostgresPoolTests(unittest.TestCase):
    def test_postgres_pool_min_max_size(self) -> None:
        with patch.dict(
            os.environ,
            {
                "GRACEKELLY_POSTGRES_POOL_MIN_SIZE": "2",
                "GRACEKELLY_POSTGRES_POOL_MAX_SIZE": "10",
            },
            clear=True,
        ):
            s = Settings.from_env()
        self.assertEqual(s.postgres_pool_min_size, 2)
        self.assertEqual(s.postgres_pool_max_size, 10)

    def test_postgres_pool_defaults(self) -> None:
        with patch.dict(os.environ, {}, clear=True):
            s = Settings.from_env()
        self.assertEqual(s.postgres_pool_min_size, 1)
        self.assertEqual(s.postgres_pool_max_size, 5)


class SettingsAnthropicTests(unittest.TestCase):
    def test_anthropic_settings_read_from_env(self) -> None:
        with patch.dict(
            os.environ,
            {
                "GRACEKELLY_ANTHROPIC_API_KEY": "sk-ant-key",
                "GRACEKELLY_ANTHROPIC_BASE_URL": "https://api.anthropic.test",
                "GRACEKELLY_ANTHROPIC_TIMEOUT_SECONDS": "90",
                "GRACEKELLY_ANTHROPIC_MAX_RETRIES": "2",
                "GRACEKELLY_ANTHROPIC_RETRY_BACKOFF_SECONDS": "2.5",
            },
            clear=True,
        ):
            s = Settings.from_env()
        self.assertEqual(s.anthropic_api_key, "sk-ant-key")
        self.assertEqual(s.anthropic_base_url, "https://api.anthropic.test")
        self.assertEqual(s.anthropic_timeout_seconds, 90.0)
        self.assertEqual(s.anthropic_max_retries, 2)
        self.assertAlmostEqual(s.anthropic_retry_backoff_seconds, 2.5)

    def test_anthropic_defaults(self) -> None:
        with patch.dict(os.environ, {}, clear=True):
            s = Settings.from_env()
        self.assertIsNone(s.anthropic_api_key)
        self.assertEqual(s.anthropic_base_url, "https://api.anthropic.com")
        self.assertEqual(s.anthropic_timeout_seconds, 120.0)
        self.assertEqual(s.anthropic_max_retries, 0)
        self.assertAlmostEqual(s.anthropic_retry_backoff_seconds, 1.0)


class SettingsMistralRetryTests(unittest.TestCase):
    def test_mistral_retry_settings(self) -> None:
        with patch.dict(
            os.environ,
            {
                "GRACEKELLY_MISTRAL_MAX_RETRIES": "3",
                "GRACEKELLY_MISTRAL_RETRY_BACKOFF_SECONDS": "0.5",
            },
            clear=True,
        ):
            s = Settings.from_env()
        self.assertEqual(s.mistral_max_retries, 3)
        self.assertAlmostEqual(s.mistral_retry_backoff_seconds, 0.5)


class SettingsBrowserScriptedTests(unittest.TestCase):
    def test_browser_scripted_model_label(self) -> None:
        with patch.dict(
            os.environ, {"GRACEKELLY_BROWSER_SCRIPTED_MODEL_LABEL": "Sonar Pro"}, clear=True
        ):
            s = Settings.from_env()
        self.assertEqual(s.browser_scripted_model_label, "Sonar Pro")

    def test_browser_scripted_model_label_default_none(self) -> None:
        with patch.dict(os.environ, {}, clear=True):
            s = Settings.from_env()
        self.assertIsNone(s.browser_scripted_model_label)

    def test_browser_scripted_output_text_custom(self) -> None:
        with patch.dict(
            os.environ,
            {"GRACEKELLY_BROWSER_SCRIPTED_OUTPUT_TEXT": "custom output"},
            clear=True,
        ):
            s = Settings.from_env()
        self.assertEqual(s.browser_scripted_output_text, "custom output")

    def test_browser_scripted_output_text_default(self) -> None:
        with patch.dict(os.environ, {}, clear=True):
            s = Settings.from_env()
        self.assertEqual(s.browser_scripted_output_text, "scripted browser result")

    def test_browser_profile_dir_set(self) -> None:
        with patch.dict(
            os.environ, {"GRACEKELLY_BROWSER_PROFILE_DIR": "/tmp/profile"}, clear=True
        ):
            s = Settings.from_env()
        self.assertEqual(s.browser_profile_dir, "/tmp/profile")

    def test_browser_profile_dir_default_none(self) -> None:
        with patch.dict(os.environ, {}, clear=True):
            s = Settings.from_env()
        self.assertIsNone(s.browser_profile_dir)


class SettingsEnvAndLogTests(unittest.TestCase):
    def test_env_development_by_default(self) -> None:
        with patch.dict(os.environ, {}, clear=True):
            s = Settings.from_env()
        self.assertEqual(s.env, "development")

    def test_env_production(self) -> None:
        with patch.dict(os.environ, {"GRACEKELLY_ENV": "production"}, clear=True):
            s = Settings.from_env()
        self.assertEqual(s.env, "production")

    def test_log_level_default_info(self) -> None:
        with patch.dict(os.environ, {}, clear=True):
            s = Settings.from_env()
        self.assertEqual(s.log_level, "INFO")

    def test_log_level_debug(self) -> None:
        with patch.dict(os.environ, {"GRACEKELLY_LOG_LEVEL": "DEBUG"}, clear=True):
            s = Settings.from_env()
        self.assertEqual(s.log_level, "DEBUG")

    def test_api_key_none_by_default(self) -> None:
        with patch.dict(os.environ, {}, clear=True):
            s = Settings.from_env()
        self.assertIsNone(s.api_key)

    def test_api_key_set(self) -> None:
        with patch.dict(os.environ, {"GRACEKELLY_API_KEY": "secret"}, clear=True):
            s = Settings.from_env()
        self.assertEqual(s.api_key, "secret")


if __name__ == "__main__":
    unittest.main()
