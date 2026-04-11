from __future__ import annotations

import os
import runpy
import sys
import unittest
from pathlib import Path
from types import ModuleType
from unittest.mock import patch

import gracekelly.config as config_module
from gracekelly.config import Settings


def _base_settings(
    *,
    storage_backend: str = "memory",
    postgres_dsn: str | None = None,
    orchestrate_timeout_seconds: float | None = None,
) -> Settings:
    return Settings(
        env="test",
        host="127.0.0.1",
        port=8011,
        log_level="INFO",
        storage_backend=storage_backend,
        postgres_dsn=postgres_dsn,
        mistral_api_key=None,
        mistral_base_url="https://api.mistral.ai/v1",
        mistral_timeout_seconds=30.0,
        openai_api_key=None,
        openai_base_url="https://api.openai.com/v1",
        openai_timeout_seconds=60.0,
        browser_enabled=False,
        browser_profile_dir=None,
        browser_base_url="https://www.perplexity.ai",
        orchestrate_timeout_seconds=orchestrate_timeout_seconds,
    )


class SettingsValidateTests(unittest.TestCase):
    def test_config_module_loads_dotenv_outside_pytest_when_available(self) -> None:
        config_path = Path(__file__).resolve().parents[1] / "src" / "gracekelly" / "config.py"
        load_calls: list[str] = []
        fake_dotenv = ModuleType("dotenv")
        setattr(fake_dotenv, "load_dotenv", lambda: load_calls.append("called"))

        with patch.dict(sys.modules, {"dotenv": fake_dotenv}, clear=False):
            sys.modules.pop("pytest", None)
            namespace = runpy.run_path(str(config_path), run_name="gracekelly_config_dotenv_test")

        self.assertIn("Settings", namespace)
        self.assertEqual(load_calls, ["called"])

    def test_config_module_ignores_missing_dotenv_outside_pytest(self) -> None:
        config_path = Path(__file__).resolve().parents[1] / "src" / "gracekelly" / "config.py"
        real_import = __import__

        def import_without_dotenv(
            name: str,
            globals: dict[str, object] | None = None,
            locals: dict[str, object] | None = None,
            fromlist: tuple[str, ...] = (),
            level: int = 0,
        ) -> object:
            if name == "dotenv":
                raise ImportError("missing dotenv")
            return real_import(name, globals, locals, fromlist, level)

        with patch.dict(sys.modules, {}, clear=False):
            sys.modules.pop("pytest", None)
            sys.modules.pop("dotenv", None)
            namespace = None
            with patch("builtins.__import__", side_effect=import_without_dotenv):
                namespace = runpy.run_path(
                    str(config_path),
                    run_name="gracekelly_config_missing_dotenv_test",
                )

        self.assertIsNotNone(namespace)
        self.assertIn("Settings", namespace)

    def test_env_bool_parses_true_false_and_default(self) -> None:
        with patch.dict(os.environ, {"GRACEKELLY_BOOL_TEST": "yes"}, clear=False):
            self.assertTrue(config_module._env_bool("GRACEKELLY_BOOL_TEST", False))

        with patch.dict(os.environ, {"GRACEKELLY_BOOL_TEST": "no"}, clear=False):
            self.assertFalse(config_module._env_bool("GRACEKELLY_BOOL_TEST", True))

        with patch.dict(os.environ, {"GRACEKELLY_BOOL_TEST": "maybe"}, clear=False):
            self.assertTrue(config_module._env_bool("GRACEKELLY_BOOL_TEST", True))

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

    def test_context_window_turns_out_of_range_raises(self) -> None:
        with self.assertRaises(ValueError) as ctx:
            Settings(context_window_turns=0).validate()

        self.assertIn("GRACEKELLY_CONTEXT_WINDOW_TURNS", str(ctx.exception))

    def test_context_window_turns_valid_range_passes(self) -> None:
        s = Settings(context_window_turns=10)
        s.validate()
        self.assertEqual(s.context_window_turns, 10)


if __name__ == "__main__":
    unittest.main()
