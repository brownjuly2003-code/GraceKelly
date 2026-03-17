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
