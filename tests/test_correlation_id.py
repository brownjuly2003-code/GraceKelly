from __future__ import annotations

import unittest
import uuid

from fastapi import FastAPI
from fastapi.testclient import TestClient

from gracekelly.middleware import setup_correlation_id


def _make_app() -> FastAPI:
    app = FastAPI()

    @app.get("/test")
    def endpoint() -> dict[str, str]:
        return {"ok": "1"}

    setup_correlation_id(app)
    return app


class CorrelationIdTests(unittest.TestCase):
    def test_generates_id_when_absent(self) -> None:
        client = TestClient(_make_app())
        resp = client.get("/test")
        self.assertIn("x-request-id", resp.headers)

    def test_generated_id_is_valid_uuid(self) -> None:
        client = TestClient(_make_app())
        resp = client.get("/test")
        req_id = resp.headers["x-request-id"]
        uuid.UUID(req_id)

    def test_echoes_client_provided_id(self) -> None:
        client = TestClient(_make_app())
        my_id = "my-request-123"
        resp = client.get("/test", headers={"x-request-id": my_id})
        self.assertEqual(resp.headers["x-request-id"], my_id)

    def test_different_requests_get_different_ids(self) -> None:
        client = TestClient(_make_app())
        id1 = client.get("/test").headers["x-request-id"]
        id2 = client.get("/test").headers["x-request-id"]
        self.assertNotEqual(id1, id2)


if __name__ == "__main__":
    unittest.main()
