from __future__ import annotations

import hmac
import logging
import re
import time
import uuid
from collections.abc import Awaitable, Callable

from fastapi import FastAPI, Request, Response
from fastapi.responses import JSONResponse

logger = logging.getLogger(__name__)

_PUBLIC_PATHS = frozenset({"/health", "/healthz/live", "/healthz/ready", "/docs", "/openapi.json", "/redoc"})


def _is_protected(path: str) -> bool:
    if path in _PUBLIC_PATHS:
        return False
    return True


def setup_api_key_auth(app: FastAPI, *, api_key: str | None) -> None:
    if not api_key:
        logger.warning("API key authentication is not configured — all endpoints are open")
        return

    expected_bearer = f"Bearer {api_key}"

    @app.middleware("http")
    async def api_key_middleware(request: Request, call_next: Callable[[Request], Awaitable[Response]]) -> Response:
        if not _is_protected(request.url.path):
            return await call_next(request)

        auth_header = request.headers.get("authorization", "")
        if hmac.compare_digest(auth_header, expected_bearer):
            return await call_next(request)

        x_api_key = request.headers.get("x-api-key", "")
        if hmac.compare_digest(x_api_key, api_key):
            return await call_next(request)

        logger.warning("api.auth.rejected path=%s", request.url.path)
        return JSONResponse(
            status_code=401,
            content={"detail": "Invalid or missing API key."},
        )


_UUID_RE = re.compile(
    r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}"
)


def _normalize_endpoint(path: str) -> str:
    return _UUID_RE.sub("{id}", path)


def setup_security_headers(app: FastAPI) -> None:
    @app.middleware("http")
    async def security_headers_middleware(request: Request, call_next: Callable[[Request], Awaitable[Response]]) -> Response:
        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["X-XSS-Protection"] = "1; mode=block"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        response.headers["Content-Security-Policy"] = "default-src 'none'"
        return response


def setup_request_metrics(app: FastAPI) -> None:
    @app.middleware("http")
    async def metrics_middleware(request: Request, call_next: Callable[[Request], Awaitable[Response]]) -> Response:
        start = time.monotonic()
        response = await call_next(request)
        duration = time.monotonic() - start
        metrics = getattr(request.app.state, "request_metrics", None)
        if metrics is not None:
            endpoint = _normalize_endpoint(request.url.path)
            metrics.record_request(endpoint, response.status_code)
            metrics.record_request_latency(endpoint, duration)
        return response


def setup_correlation_id(app: FastAPI) -> None:
    @app.middleware("http")
    async def correlation_id_middleware(
        request: Request, call_next: Callable[[Request], Awaitable[Response]]
    ) -> Response:
        req_id = request.headers.get("x-request-id") or str(uuid.uuid4())
        response = await call_next(request)
        response.headers["X-Request-ID"] = req_id
        return response
