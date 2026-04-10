from __future__ import annotations

import builtins
import os
import sys
import types
import unittest
from unittest.mock import MagicMock, patch

from gracekelly.config import Settings
from gracekelly.middleware import logger, setup_sentry


class SentrySetupTests(unittest.TestCase):
    def test_setup_sentry_initializes_sdk_when_dsn_is_provided(self) -> None:
        mock_sentry = types.ModuleType("sentry_sdk")
        mock_sentry.init = MagicMock()  # type: ignore[attr-defined]
        integrations = types.ModuleType("sentry_sdk.integrations")
        fastapi_module = types.ModuleType("sentry_sdk.integrations.fastapi")
        starlette_module = types.ModuleType("sentry_sdk.integrations.starlette")

        class FastApiIntegration:
            pass

        class StarletteIntegration:
            pass

        fastapi_module.FastApiIntegration = FastApiIntegration  # type: ignore[attr-defined]
        starlette_module.StarletteIntegration = StarletteIntegration  # type: ignore[attr-defined]

        with patch.dict(
            sys.modules,
            {
                "sentry_sdk": mock_sentry,
                "sentry_sdk.integrations": integrations,
                "sentry_sdk.integrations.fastapi": fastapi_module,
                "sentry_sdk.integrations.starlette": starlette_module,
            },
        ):
            setup_sentry("https://key@sentry.io/123", "test")

        mock_sentry.init.assert_called_once()
        _, kwargs = mock_sentry.init.call_args
        self.assertEqual(kwargs["dsn"], "https://key@sentry.io/123")
        self.assertEqual(kwargs["environment"], "test")
        self.assertEqual(kwargs["traces_sample_rate"], 0.1)
        self.assertFalse(kwargs["send_default_pii"])
        self.assertEqual(len(kwargs["integrations"]), 2)

    def test_setup_sentry_returns_without_importing_sdk_when_dsn_is_missing(self) -> None:
        real_import = builtins.__import__
        imported_names: list[str] = []

        def import_spy(
            name: str,
            globals_: dict[str, object] | None = None,
            locals_: dict[str, object] | None = None,
            fromlist: tuple[str, ...] = (),
            level: int = 0,
        ) -> object:
            imported_names.append(name)
            return real_import(name, globals_, locals_, fromlist, level)

        with patch("builtins.__import__", side_effect=import_spy):
            setup_sentry(None, "production")

        self.assertNotIn("sentry_sdk", imported_names)

    def test_setup_sentry_returns_silently_when_sdk_is_not_installed(self) -> None:
        with patch.dict(sys.modules, {"sentry_sdk": None}):
            with patch.object(logger, "warning") as warning_mock:
                setup_sentry("https://key@sentry.io/123")

        warning_mock.assert_called_once()

    def test_settings_reads_sentry_fields_from_env(self) -> None:
        with patch.dict(
            os.environ,
            {
                "GRACEKELLY_SENTRY_DSN": "https://x@sentry.io/1",
                "GRACEKELLY_SENTRY_ENVIRONMENT": "staging",
            },
            clear=False,
        ):
            settings = Settings.from_env()

        self.assertEqual(settings.sentry_dsn, "https://x@sentry.io/1")
        self.assertEqual(settings.sentry_environment, "staging")
