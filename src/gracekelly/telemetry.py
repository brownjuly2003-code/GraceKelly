from __future__ import annotations

import logging
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from fastapi import FastAPI

logger = logging.getLogger(__name__)


def setup_telemetry(
    app: FastAPI,
    endpoint: str | None,
    service_name: str = "gracekelly",
) -> None:
    """Configure OpenTelemetry if endpoint is set and SDK is installed."""
    if not endpoint:
        return
    try:
        from opentelemetry import trace
        from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
        from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
        from opentelemetry.sdk.resources import Resource
        from opentelemetry.sdk.trace import TracerProvider
        from opentelemetry.sdk.trace.export import BatchSpanProcessor
    except ImportError:
        logger.warning(
            "GRACEKELLY_OTEL_ENDPOINT is set but opentelemetry SDK is not installed. "
            "Install with: pip install 'gracekelly[observability]'"
        )
        return

    resource = Resource.create({"service.name": service_name})
    provider = TracerProvider(resource=resource)
    exporter = OTLPSpanExporter(endpoint=endpoint)
    provider.add_span_processor(BatchSpanProcessor(exporter))
    trace.set_tracer_provider(provider)
    FastAPIInstrumentor.instrument_app(app)
    logger.info("OpenTelemetry initialized (endpoint=%s, service=%s)", endpoint, service_name)
