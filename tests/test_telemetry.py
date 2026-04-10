from __future__ import annotations

import builtins
import os
import sys
import types
import unittest
from typing import Any
from unittest.mock import MagicMock, patch

from fastapi import FastAPI

from gracekelly.config import Settings
from gracekelly.telemetry import logger, setup_telemetry


class TelemetrySetupTests(unittest.TestCase):
    def test_no_op_when_endpoint_is_none(self) -> None:
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
            setup_telemetry(FastAPI(), None)

        self.assertFalse(any(name.startswith("opentelemetry") for name in imported_names))

    def test_no_op_with_warning_when_sdk_not_installed(self) -> None:
        with patch.dict(sys.modules, {"opentelemetry": None}):
            with patch.object(logger, "warning") as warning_mock:
                setup_telemetry(FastAPI(), "https://otel.example/v1/traces")

        warning_mock.assert_called_once()

    def test_tracer_provider_set_when_sdk_available(self) -> None:
        opentelemetry_module: Any = types.ModuleType("opentelemetry")
        trace_module: Any = types.ModuleType("opentelemetry.trace")
        trace_module.set_tracer_provider = MagicMock()
        opentelemetry_module.trace = trace_module

        exporter_package: Any = types.ModuleType("opentelemetry.exporter")
        otlp_package: Any = types.ModuleType("opentelemetry.exporter.otlp")
        proto_package: Any = types.ModuleType("opentelemetry.exporter.otlp.proto")
        http_package: Any = types.ModuleType("opentelemetry.exporter.otlp.proto.http")
        trace_exporter_module: Any = types.ModuleType("opentelemetry.exporter.otlp.proto.http.trace_exporter")
        exporter_instance = MagicMock()
        trace_exporter_module.OTLPSpanExporter = MagicMock(return_value=exporter_instance)
        exporter_package.otlp = otlp_package
        otlp_package.proto = proto_package
        proto_package.http = http_package
        http_package.trace_exporter = trace_exporter_module

        instrumentation_package: Any = types.ModuleType("opentelemetry.instrumentation")
        fastapi_instrumentation_module: Any = types.ModuleType("opentelemetry.instrumentation.fastapi")
        fastapi_instrumentation_module.FastAPIInstrumentor = types.SimpleNamespace(instrument_app=MagicMock())
        instrumentation_package.fastapi = fastapi_instrumentation_module

        sdk_package: Any = types.ModuleType("opentelemetry.sdk")
        resources_module: Any = types.ModuleType("opentelemetry.sdk.resources")
        resource = object()
        resources_module.Resource = types.SimpleNamespace(create=MagicMock(return_value=resource))
        trace_sdk_module: Any = types.ModuleType("opentelemetry.sdk.trace")
        provider = MagicMock()
        trace_sdk_module.TracerProvider = MagicMock(return_value=provider)
        trace_export_module: Any = types.ModuleType("opentelemetry.sdk.trace.export")
        span_processor = object()
        trace_export_module.BatchSpanProcessor = MagicMock(return_value=span_processor)
        sdk_package.resources = resources_module
        sdk_package.trace = trace_sdk_module
        trace_sdk_module.export = trace_export_module

        with patch.dict(
            sys.modules,
            {
                "opentelemetry": opentelemetry_module,
                "opentelemetry.trace": trace_module,
                "opentelemetry.exporter": exporter_package,
                "opentelemetry.exporter.otlp": otlp_package,
                "opentelemetry.exporter.otlp.proto": proto_package,
                "opentelemetry.exporter.otlp.proto.http": http_package,
                "opentelemetry.exporter.otlp.proto.http.trace_exporter": trace_exporter_module,
                "opentelemetry.instrumentation": instrumentation_package,
                "opentelemetry.instrumentation.fastapi": fastapi_instrumentation_module,
                "opentelemetry.sdk": sdk_package,
                "opentelemetry.sdk.resources": resources_module,
                "opentelemetry.sdk.trace": trace_sdk_module,
                "opentelemetry.sdk.trace.export": trace_export_module,
            },
        ):
            setup_telemetry(FastAPI(), "https://otel.example/v1/traces", "gracekelly-api")

        trace_module.set_tracer_provider.assert_called_once_with(provider)

    def test_fastapi_instrumented_when_sdk_available(self) -> None:
        opentelemetry_module: Any = types.ModuleType("opentelemetry")
        trace_module: Any = types.ModuleType("opentelemetry.trace")
        trace_module.set_tracer_provider = MagicMock()
        opentelemetry_module.trace = trace_module

        exporter_package: Any = types.ModuleType("opentelemetry.exporter")
        otlp_package: Any = types.ModuleType("opentelemetry.exporter.otlp")
        proto_package: Any = types.ModuleType("opentelemetry.exporter.otlp.proto")
        http_package: Any = types.ModuleType("opentelemetry.exporter.otlp.proto.http")
        trace_exporter_module: Any = types.ModuleType("opentelemetry.exporter.otlp.proto.http.trace_exporter")
        trace_exporter_module.OTLPSpanExporter = MagicMock(return_value=MagicMock())
        exporter_package.otlp = otlp_package
        otlp_package.proto = proto_package
        proto_package.http = http_package
        http_package.trace_exporter = trace_exporter_module

        instrumentation_package: Any = types.ModuleType("opentelemetry.instrumentation")
        fastapi_instrumentation_module: Any = types.ModuleType("opentelemetry.instrumentation.fastapi")
        instrument_app = MagicMock()
        fastapi_instrumentation_module.FastAPIInstrumentor = types.SimpleNamespace(instrument_app=instrument_app)
        instrumentation_package.fastapi = fastapi_instrumentation_module

        sdk_package: Any = types.ModuleType("opentelemetry.sdk")
        resources_module: Any = types.ModuleType("opentelemetry.sdk.resources")
        resources_module.Resource = types.SimpleNamespace(create=MagicMock(return_value=object()))
        trace_sdk_module: Any = types.ModuleType("opentelemetry.sdk.trace")
        trace_sdk_module.TracerProvider = MagicMock(return_value=MagicMock())
        trace_export_module: Any = types.ModuleType("opentelemetry.sdk.trace.export")
        trace_export_module.BatchSpanProcessor = MagicMock(return_value=object())
        sdk_package.resources = resources_module
        sdk_package.trace = trace_sdk_module
        trace_sdk_module.export = trace_export_module

        app = FastAPI()

        with patch.dict(
            sys.modules,
            {
                "opentelemetry": opentelemetry_module,
                "opentelemetry.trace": trace_module,
                "opentelemetry.exporter": exporter_package,
                "opentelemetry.exporter.otlp": otlp_package,
                "opentelemetry.exporter.otlp.proto": proto_package,
                "opentelemetry.exporter.otlp.proto.http": http_package,
                "opentelemetry.exporter.otlp.proto.http.trace_exporter": trace_exporter_module,
                "opentelemetry.instrumentation": instrumentation_package,
                "opentelemetry.instrumentation.fastapi": fastapi_instrumentation_module,
                "opentelemetry.sdk": sdk_package,
                "opentelemetry.sdk.resources": resources_module,
                "opentelemetry.sdk.trace": trace_sdk_module,
                "opentelemetry.sdk.trace.export": trace_export_module,
            },
        ):
            setup_telemetry(app, "https://otel.example/v1/traces")

        instrument_app.assert_called_once_with(app)

    def test_settings_reads_otel_env_vars(self) -> None:
        with patch.dict(
            os.environ,
            {
                "GRACEKELLY_OTEL_ENDPOINT": "https://otel.example/v1/traces",
                "GRACEKELLY_OTEL_SERVICE_NAME": "gracekelly-worker",
            },
            clear=True,
        ):
            settings = Settings.from_env()

        self.assertEqual(settings.otel_endpoint, "https://otel.example/v1/traces")
        self.assertEqual(settings.otel_service_name, "gracekelly-worker")
