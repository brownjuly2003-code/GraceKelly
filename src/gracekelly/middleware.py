from __future__ import annotations

import hmac
import logging
import time
from collections import defaultdict
from threading import Lock
from typing import Callable

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


class RateLimiter:
    def __init__(self, *, requests_per_minute: int) -> None:
        self._limit = requests_per_minute
        self._window_seconds = 60.0
        self._lock = Lock()
        self._buckets: dict[str, list[float]] = defaultdict(list)

    def is_allowed(self, client_id: str) -> bool:
        now = time.monotonic()
        cutoff = now - self._window_seconds
        with self._lock:
            timestamps = self._buckets[client_id]
            recent = [t for t in timestamps if t > cutoff]
            if not recent:
                del self._buckets[client_id]
                self._buckets[client_id] = [now]
                return True
            if len(recent) >= self._limit:
                self._buckets[client_id] = recent
                return False
            recent.append(now)
            self._buckets[client_id] = recent
            return True


def setup_rate_limiting(app: FastAPI, *, requests_per_minute: int | None) -> None:
    if not requests_per_minute or requests_per_minute <= 0:
        logger.warning("Rate limiting is not configured — no per-IP request limits")
        return

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
