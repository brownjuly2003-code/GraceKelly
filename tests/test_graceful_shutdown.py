from __future__ import annotations

import asyncio
import unittest

from fastapi import FastAPI
from fastapi.testclient import TestClient

from gracekelly.config import Settings
from gracekelly.main import create_app
from gracekelly.middleware import setup_request_tracking


class RequestTrackingTests(unittest.TestCase):
    def test_active_requests_tracked_increments_and_decrements(self) -> None:
        """Counter is 0 before and after each completed request."""
        # We verify the counter via setup_request_tracking on a fresh mini-app.
        # Uses a sync handler to avoid pytest-asyncio STRICT event-loop conflicts
        # that prevent async closures from capturing values in unittest context.
        mini = FastAPI()
        setup_request_tracking(mini)

        @mini.get("/probe")
        def _probe() -> dict[str, object]:
            captured.append(getattr(mini.state, "_active_requests", 0))
            return {"ok": True}

        captured: list[int] = []
        client = TestClient(mini, raise_server_exceptions=True)
        self.assertEqual(getattr(mini.state, "_active_requests", 0), 0)
        resp = client.get("/probe")
        self.assertEqual(resp.status_code, 200)
        # During the request the counter was at least 1
        self.assertTrue(any(v >= 1 for v in captured), f"Expected >=1 during request, got {captured}")
        # After the request it must be back to 0
        self.assertEqual(getattr(mini.state, "_active_requests", 0), 0)

    def test_active_requests_zero_before_any_request(self) -> None:
        app = create_app(Settings())
        self.assertEqual(getattr(app.state, "_active_requests", 0), 0)

    def test_counter_resets_to_zero_after_multiple_requests(self) -> None:
        app = create_app(Settings())
        client = TestClient(app, raise_server_exceptions=True)
        for _ in range(5):
            client.get("/health")
        self.assertEqual(getattr(app.state, "_active_requests", 0), 0)

    def test_setup_request_tracking_standalone(self) -> None:
        """setup_request_tracking works on a bare FastAPI app."""
        mini = FastAPI()
        setup_request_tracking(mini)

        @mini.get("/ping")
        async def ping() -> dict[str, str]:
            return {"pong": "true"}

        client = TestClient(mini)
        client.get("/ping")
        self.assertEqual(getattr(mini.state, "_active_requests", 0), 0)


class DrainPeriodTests(unittest.IsolatedAsyncioTestCase):
    async def test_drain_completes_immediately_when_no_active_requests(self) -> None:
        """Lifespan drain exits immediately if _active_requests is 0."""
        from gracekelly.main import app_lifespan

        app = FastAPI(lifespan=app_lifespan)
        app.state.settings = Settings(graceful_shutdown_timeout_seconds=1.0)
        app.state._active_requests = 0

        # Run the shutdown side of the lifespan (after yield)
        ctx = app_lifespan(app)
        await ctx.__aenter__()
        start = asyncio.get_event_loop().time()
        await ctx.__aexit__(None, None, None)
        elapsed = asyncio.get_event_loop().time() - start

        # Should complete well under the 1 s timeout since there are no active requests
        self.assertLess(elapsed, 0.5)

    async def test_drain_times_out_when_requests_stuck(self) -> None:
        """Lifespan drain respects graceful_shutdown_timeout_seconds."""
        from gracekelly.main import app_lifespan

        app = FastAPI(lifespan=app_lifespan)
        app.state.settings = Settings(graceful_shutdown_timeout_seconds=0.1)
        # Simulate a stuck request
        app.state._active_requests = 1

        ctx = app_lifespan(app)
        await ctx.__aenter__()
        start = asyncio.get_event_loop().time()
        await ctx.__aexit__(None, None, None)
        elapsed = asyncio.get_event_loop().time() - start

        # Must have waited approximately the timeout, then given up
        self.assertGreaterEqual(elapsed, 0.1)
        # But not forever
        self.assertLess(elapsed, 2.0)
