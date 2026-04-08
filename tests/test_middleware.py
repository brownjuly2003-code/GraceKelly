from __future__ import annotations

import unittest

from fastapi import FastAPI
from fastapi.testclient import TestClient

from gracekelly.middleware import setup_api_key_auth, setup_security_headers


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


def _test_app(*, api_key: str | None = None) -> FastAPI:
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
