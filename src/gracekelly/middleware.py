from __future__ import annotations

import hmac
import logging
import time
from collections import defaultdict
from collections.abc import Callable
from threading import Lock

from fastapi import FastAPI, Request, Response
from fastapi.responses import JSONResponse

logger = logging.getLogger(__name__)

_PUBLIC_PATHS = frozenset({"/health", "/docs", "/openapi.json", "/redoc"})


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
    async def api_key_middleware(request: Request, call_next: Callable) -> Response:
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


_PURGE_EVERY_N_REQUESTS = 500


class RateLimiter:
    """In-process sliding-window rate limiter.

    NOTE: Works correctly only within a single process. Multiple uvicorn
    workers or multiple service instances will each maintain their own
    independent counters — effective limit becomes limit × worker_count.
    Use a Redis-backed limiter for multi-process deployments.
    """

    def __init__(self, *, requests_per_minute: int) -> None:
        self._limit = requests_per_minute
        self._window_seconds = 60.0
        self._lock = Lock()
        self._buckets: dict[str, list[float]] = defaultdict(list)
        self._request_count = 0

    def is_allowed(self, client_id: str) -> bool:
        now = time.monotonic()
        cutoff = now - self._window_seconds
        with self._lock:
            self._request_count += 1
            if self._request_count >= _PURGE_EVERY_N_REQUESTS:
                self._purge_stale(now)
                self._request_count = 0
            timestamps = self._buckets[client_id]
            recent = [t for t in timestamps if t > cutoff]
            if not recent:
                self._buckets[client_id] = [now]
                return True
            if len(recent) >= self._limit:
                self._buckets[client_id] = recent
                return False
            recent.append(now)
            self._buckets[client_id] = recent
            return True

    def _purge_stale(self, now: float) -> None:
        cutoff = now - self._window_seconds
        stale_keys = [k for k, ts in self._buckets.items() if not ts or max(ts) < cutoff]
        for k in stale_keys:
            del self._buckets[k]


_UUID_RE = __import__("re").compile(
    r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}"
)


def _normalize_endpoint(path: str) -> str:
    return _UUID_RE.sub("{id}", path)


def setup_security_headers(app: FastAPI) -> None:
    @app.middleware("http")
    async def security_headers_middleware(request: Request, call_next: Callable) -> Response:
        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["X-XSS-Protection"] = "1; mode=block"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        response.headers["Content-Security-Policy"] = "default-src 'none'"
        return response


def setup_request_metrics(app: FastAPI) -> None:
    @app.middleware("http")
    async def metrics_middleware(request: Request, call_next: Callable) -> Response:
        response = await call_next(request)
        metrics = getattr(request.app.state, "request_metrics", None)
        if metrics is not None:
            endpoint = _normalize_endpoint(request.url.path)
            metrics.record_request(endpoint, response.status_code)
        return response


def setup_rate_limiting(app: FastAPI, *, requests_per_minute: int | None) -> None:
    if not requests_per_minute or requests_per_minute <= 0:
        logger.warning("Rate limiting is not configured — no per-IP request limits")
        return

    logger.warning(
        "Rate limiting enabled at %d req/min — in-process only, "
        "does not coordinate across multiple workers or instances",
        requests_per_minute,
    )
    limiter = RateLimiter(requests_per_minute=requests_per_minute)

    @app.middleware("http")
    async def rate_limit_middleware(request: Request, call_next: Callable) -> Response:
        if not _is_protected(request.url.path):
            return await call_next(request)

        client_ip = request.client.host if request.client else "unknown"
        if not limiter.is_allowed(client_ip):
            logger.warning("api.rate_limited client=%s path=%s", client_ip, request.url.path)
            return JSONResponse(
                status_code=429,
                content={"detail": "Rate limit exceeded. Try again later."},
            )

        return await call_next(request)
