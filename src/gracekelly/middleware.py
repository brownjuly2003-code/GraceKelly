from __future__ import annotations

import hashlib
import hmac
import json
import logging
import pathlib
import re
import threading
import time
import uuid
from collections.abc import Awaitable, Callable
from datetime import UTC, datetime

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
        response.headers["Content-Security-Policy"] = (
            "default-src 'self'; "
            "script-src 'self'; "
            "style-src 'self'; "
            "connect-src 'self'; "
            "img-src 'self' data: blob:; "
            "font-src 'self'; "
            "object-src 'none'; "
            "frame-src 'none'; "
            "base-uri 'self'; "
            "form-action 'self'"
        )
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


def setup_rate_limiting(app: FastAPI, redis_url: str | None, rpm: int = 60, burst: int = 10) -> None:
    if not redis_url:
        return
    try:
        import redis.asyncio as aioredis
    except ImportError:
        logger.warning(
            "GRACEKELLY_REDIS_URL is set but redis package is not installed. "
            "Install with: pip install 'gracekelly[redis]'"
        )
        return

    _redis_client = aioredis.from_url(redis_url, decode_responses=True)
    _window_seconds = 60

    @app.middleware("http")
    async def rate_limit_middleware(
        request: Request, call_next: Callable[[Request], Awaitable[Response]]
    ) -> Response:
        if request.url.path in _PUBLIC_PATHS:
            return await call_next(request)

        client_ip = request.client.host if request.client else "unknown"
        key = f"gracekelly:rl:{client_ip}"
        now = time.time()
        window_start = now - _window_seconds

        try:
            pipe = _redis_client.pipeline()
            pipe.zremrangebyscore(key, 0, window_start)
            pipe.zadd(key, {str(now): now})
            pipe.zcard(key)
            pipe.expire(key, _window_seconds + 1)
            results = await pipe.execute()
            request_count = results[2]
        except Exception:
            return await call_next(request)

        effective_limit = rpm + burst
        if request_count > effective_limit:
            return JSONResponse(
                status_code=429,
                content={
                    "type": "about:blank",
                    "title": "Too Many Requests",
                    "status": 429,
                    "detail": f"Rate limit exceeded: {rpm} requests/minute allowed.",
                },
                headers={"Retry-After": str(_window_seconds)},
            )
        return await call_next(request)

    logger.info("Redis rate limiting enabled (url=%s, rpm=%d)", redis_url, rpm)


_PROMPT_HASH_ROUTES = frozenset(
    {
        "/api/v1/orchestrate",
        "/api/v1/orchestrate/upload",
        "/api/v1/orchestrate/stream",
        "/api/v1/consensus",
        "/api/v1/compare",
        "/api/v1/debate",
        "/api/v1/smart",
        "/api/v1/smart/v2",
        "/api/v1/batch",
        "/api/v1/pipeline",
    }
)


def setup_usage_telemetry(app: FastAPI, *, enabled: bool, log_path: str | None) -> None:
    if not enabled:
        return

    resolved = pathlib.Path(log_path).expanduser() if log_path else pathlib.Path("logs") / "usage.jsonl"
    try:
        resolved.parent.mkdir(parents=True, exist_ok=True)
    except OSError as exc:
        logger.warning("usage_telemetry.parent_dir_failed path=%s error=%r", resolved, exc)
        return

    write_lock = threading.Lock()
    write_failed_warned = False

    @app.middleware("http")
    async def usage_telemetry_middleware(
        request: Request, call_next: Callable[[Request], Awaitable[Response]]
    ) -> Response:
        nonlocal write_failed_warned

        prompt_hash: str | None = None
        if request.method == "POST" and request.url.path in _PROMPT_HASH_ROUTES:
            try:
                body_bytes = await request.body()
                if body_bytes:
                    prompt_hash = hashlib.sha256(body_bytes).hexdigest()

                async def _replay_receive() -> dict[str, object]:
                    return {"type": "http.request", "body": body_bytes, "more_body": False}

                request._receive = _replay_receive
            except Exception:  # noqa: BLE001 — telemetry must never block the request
                pass

        start = time.monotonic()
        response = await call_next(request)
        duration_ms = int((time.monotonic() - start) * 1000)

        request_id = response.headers.get("x-request-id") or request.headers.get("x-request-id")
        record: dict[str, object] = {
            "ts": datetime.now(UTC).isoformat().replace("+00:00", "Z"),
            "endpoint": _normalize_endpoint(request.url.path),
            "method": request.method,
            "status": response.status_code,
            "duration_ms": duration_ms,
            "request_id": request_id,
            "prompt_hash": prompt_hash,
        }

        line = json.dumps(record, ensure_ascii=False) + "\n"
        try:
            with write_lock, resolved.open("a", encoding="utf-8") as fh:
                fh.write(line)
        except Exception as exc:  # noqa: BLE001 — telemetry must never break the response
            if not write_failed_warned:
                logger.warning("usage_telemetry.write_failed path=%s error=%r", resolved, exc)
                write_failed_warned = True

        return response


def setup_sentry(dsn: str | None, environment: str = "production") -> None:
    if not dsn:
        return
    try:
        import sentry_sdk
        from sentry_sdk.integrations.fastapi import FastApiIntegration
        from sentry_sdk.integrations.starlette import StarletteIntegration
    except ImportError:
        logger.warning(
            "GRACEKELLY_SENTRY_DSN is set but sentry-sdk is not installed. "
            "Install with: pip install 'gracekelly[observability]'"
        )
        return
    sentry_sdk.init(
        dsn=dsn,
        environment=environment,
        integrations=[StarletteIntegration(), FastApiIntegration()],
        traces_sample_rate=0.1,
        send_default_pii=False,
    )
    logger.info("Sentry initialized (environment=%s)", environment)
