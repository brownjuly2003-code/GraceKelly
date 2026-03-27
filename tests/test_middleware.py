from __future__ import annotations

import unittest

from fastapi import FastAPI
from fastapi.testclient import TestClient

from gracekelly.middleware import RateLimiter, setup_api_key_auth, setup_rate_limiting, setup_security_headers


def _test_app_with_security_headers() -> FastAPI:
    app = FastAPI()

    @app.get("/health")
    def health():
        return {"status": "ok"}

    @app.get("/api/v1/models")
    def models():
        return []

    setup_security_headers(app)
    return app


def _test_app(*, api_key: str | None = None, rate_limit: int | None = None) -> FastAPI:
    app = FastAPI()

    @app.get("/health")
    def health():
        return {"status": "ok"}

    @app.get("/api/v1/models")
    def models():
        return []

    @app.post("/api/v1/orchestrate")
    def orchestrate():
        return {"task_id": "t1"}

    @app.get("/api/v1/readiness")
    def readiness():
        return {"status": "ok"}

    @app.get("/metrics")
    def metrics():
        return "metrics"

    setup_api_key_auth(app, api_key=api_key)
    setup_rate_limiting(app, requests_per_minute=rate_limit)
    return app


class ApiKeyAuthTests(unittest.TestCase):
    def test_no_key_configured_allows_all(self) -> None:
        client = TestClient(_test_app(api_key=None))
        response = client.get("/api/v1/models")
        self.assertEqual(response.status_code, 200)

    def test_health_always_public(self) -> None:
        client = TestClient(_test_app(api_key="secret"))
        response = client.get("/health")
        self.assertEqual(response.status_code, 200)

    def test_protected_endpoint_rejects_without_key(self) -> None:
        client = TestClient(_test_app(api_key="secret"))
        response = client.get("/api/v1/models")
        self.assertEqual(response.status_code, 401)
        self.assertIn("API key", response.json()["detail"])

    def test_bearer_token_auth(self) -> None:
        client = TestClient(_test_app(api_key="secret"))
        response = client.get(
            "/api/v1/models",
            headers={"Authorization": "Bearer secret"},
        )
        self.assertEqual(response.status_code, 200)

    def test_x_api_key_header(self) -> None:
        client = TestClient(_test_app(api_key="secret"))
        response = client.get(
            "/api/v1/models",
            headers={"X-API-Key": "secret"},
        )
        self.assertEqual(response.status_code, 200)

    def test_wrong_key_rejected(self) -> None:
        client = TestClient(_test_app(api_key="secret"))
        response = client.get(
            "/api/v1/models",
            headers={"Authorization": "Bearer wrong"},
        )
        self.assertEqual(response.status_code, 401)

    def test_post_endpoint_protected(self) -> None:
        client = TestClient(_test_app(api_key="secret"))
        response = client.post("/api/v1/orchestrate")
        self.assertEqual(response.status_code, 401)

    def test_readiness_protected(self) -> None:
        client = TestClient(_test_app(api_key="secret"))
        response = client.get("/api/v1/readiness")
        self.assertEqual(response.status_code, 401)

    def test_metrics_protected(self) -> None:
        client = TestClient(_test_app(api_key="secret"))
        response = client.get("/metrics")
        self.assertEqual(response.status_code, 401)


class RateLimiterUnitTests(unittest.TestCase):
    def test_allows_within_limit(self) -> None:
        limiter = RateLimiter(requests_per_minute=5)
        for _ in range(5):
            self.assertTrue(limiter.is_allowed("client1"))

    def test_blocks_over_limit(self) -> None:
        limiter = RateLimiter(requests_per_minute=3)
        for _ in range(3):
            limiter.is_allowed("client1")
        self.assertFalse(limiter.is_allowed("client1"))

    def test_independent_clients(self) -> None:
        limiter = RateLimiter(requests_per_minute=2)
        limiter.is_allowed("client1")
        limiter.is_allowed("client1")
        self.assertFalse(limiter.is_allowed("client1"))
        self.assertTrue(limiter.is_allowed("client2"))

    def test_purge_stale_removes_expired_buckets(self) -> None:
        import time as _time

        limiter = RateLimiter(requests_per_minute=100)
        limiter.is_allowed("old-client")
        # Manually backdate the bucket to simulate expiry
        with limiter._lock:
            limiter._buckets["old-client"] = [_time.monotonic() - 120]
        with limiter._lock:
            limiter._purge_stale(_time.monotonic())
        with limiter._lock:
            self.assertNotIn("old-client", limiter._buckets)

    def test_active_bucket_not_purged(self) -> None:
        limiter = RateLimiter(requests_per_minute=100)
        limiter.is_allowed("active-client")
        import time as _time
        with limiter._lock:
            limiter._purge_stale(_time.monotonic())
        with limiter._lock:
            self.assertIn("active-client", limiter._buckets)


class RateLimitMiddlewareTests(unittest.TestCase):
    def test_no_limit_allows_all(self) -> None:
        client = TestClient(_test_app(rate_limit=None))
        for _ in range(100):
            response = client.get("/api/v1/models")
            self.assertEqual(response.status_code, 200)

    def test_limit_enforced(self) -> None:
        client = TestClient(_test_app(rate_limit=3))
        for _ in range(3):
            response = client.get("/api/v1/models")
            self.assertEqual(response.status_code, 200)
        response = client.get("/api/v1/models")
        self.assertEqual(response.status_code, 429)
        self.assertIn("Rate limit", response.json()["detail"])

    def test_health_exempt_from_rate_limit(self) -> None:
        client = TestClient(_test_app(rate_limit=2))
        client.get("/api/v1/models")
        client.get("/api/v1/models")
        response = client.get("/health")
        self.assertEqual(response.status_code, 200)


class CombinedMiddlewareTests(unittest.TestCase):
    def test_auth_checked_before_rate_limit(self) -> None:
        client = TestClient(_test_app(api_key="secret", rate_limit=100))
        response = client.get("/api/v1/models")
        self.assertEqual(response.status_code, 401)

    def test_auth_plus_rate_limit(self) -> None:
        client = TestClient(_test_app(api_key="secret", rate_limit=2))
        headers = {"Authorization": "Bearer secret"}
        self.assertEqual(client.get("/api/v1/models", headers=headers).status_code, 200)
        self.assertEqual(client.get("/api/v1/models", headers=headers).status_code, 200)
        self.assertEqual(client.get("/api/v1/models", headers=headers).status_code, 429)


class SecurityHeadersTests(unittest.TestCase):
    def setUp(self) -> None:
        self.client = TestClient(_test_app_with_security_headers())

    def test_x_content_type_options(self) -> None:
        resp = self.client.get("/health")
        self.assertEqual(resp.headers.get("x-content-type-options"), "nosniff")

    def test_x_frame_options(self) -> None:
        resp = self.client.get("/health")
        self.assertEqual(resp.headers.get("x-frame-options"), "DENY")

    def test_x_xss_protection(self) -> None:
        resp = self.client.get("/health")
        self.assertEqual(resp.headers.get("x-xss-protection"), "1; mode=block")

    def test_referrer_policy(self) -> None:
        resp = self.client.get("/health")
        self.assertEqual(resp.headers.get("referrer-policy"), "strict-origin-when-cross-origin")

    def test_content_security_policy(self) -> None:
        resp = self.client.get("/health")
        self.assertEqual(resp.headers.get("content-security-policy"), "default-src 'none'")

    def test_headers_present_on_api_endpoint(self) -> None:
        resp = self.client.get("/api/v1/models")
        self.assertIn("x-content-type-options", resp.headers)
        self.assertIn("x-frame-options", resp.headers)
