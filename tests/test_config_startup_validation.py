from __future__ import annotations

import unittest

from gracekelly.config import Settings


def _base_settings(**kwargs: object) -> Settings:
    data: dict[str, object] = {
        "env": "test",
        "host": "127.0.0.1",
        "port": 8011,
        "log_level": "INFO",
        "storage_backend": "memory",
        "postgres_dsn": None,
        "mistral_api_key": None,
        "mistral_base_url": "https://api.mistral.ai/v1",
        "mistral_timeout_seconds": 30.0,
        "openai_api_key": None,
        "openai_base_url": "https://api.openai.com/v1",
        "openai_timeout_seconds": 60.0,
        "browser_enabled": False,
        "browser_profile_dir": None,
        "browser_base_url": "https://www.perplexity.ai",
    }
    data.update(kwargs)
    return Settings(**data)


class SettingsValidateTests(unittest.TestCase):
    def test_valid_memory_config_passes(self) -> None:
        s = _base_settings()
        s.validate()

    def test_postgres_without_dsn_raises(self) -> None:
        s = _base_settings(storage_backend="postgres", postgres_dsn=None)
        with self.assertRaises(ValueError) as ctx:
            s.validate()
        self.assertIn("GRACEKELLY_POSTGRES_DSN", str(ctx.exception))

    def test_postgres_with_dsn_passes(self) -> None:
        s = _base_settings(storage_backend="postgres", postgres_dsn="postgresql://u:p@h/db")
        s.validate()

    def test_timeout_non_positive_raises(self) -> None:
        s = _base_settings(orchestrate_timeout_seconds=0.0)
        with self.assertRaises(ValueError) as ctx:
            s.validate()
        self.assertIn("GRACEKELLY_ORCHESTRATE_TIMEOUT_SECONDS", str(ctx.exception))

    def test_timeout_none_passes(self) -> None:
        s = _base_settings(orchestrate_timeout_seconds=None)
        s.validate()

    def test_subsecond_timeout_passes(self) -> None:
        s = _base_settings(orchestrate_timeout_seconds=0.5)
        s.validate()


if __name__ == "__main__":
    unittest.main()
