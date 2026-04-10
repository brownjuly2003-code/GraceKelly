from __future__ import annotations

import sys
import types
import unittest
from unittest.mock import AsyncMock, Mock, patch

from fastapi import FastAPI
from fastapi.testclient import TestClient

from gracekelly.middleware import setup_rate_limiting


class RedisRateLimitTests(unittest.TestCase):
    def test_no_op_when_redis_url_is_none(self) -> None:
        app = FastAPI()

        @app.get("/private")
        async def private() -> dict[str, bool]:
            return {"ok": True}

        with patch("builtins.__import__", wraps=__import__) as import_mock:
            setup_rate_limiting(app, None, rpm=60, burst=10)

        self.assertEqual(len(app.user_middleware), 0)
        self.assertFalse(any(call.args and call.args[0] == "redis.asyncio" for call in import_mock.call_args_list))
        with TestClient(app) as client:
            response = client.get("/private")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"ok": True})

    def test_no_op_with_warning_when_redis_not_installed(self) -> None:
        app = FastAPI()
        redis_package = types.ModuleType("redis")
        redis_package.__path__ = []

        with patch.dict(
            sys.modules,
            {"redis": redis_package, "redis.asyncio": None},
            clear=False,
        ):
            with patch("gracekelly.middleware.logger.warning") as warning_mock:
                setup_rate_limiting(app, "redis://localhost:6379/0", rpm=60, burst=10)

        self.assertEqual(len(app.user_middleware), 0)
        warning_mock.assert_called_once()
        self.assertIn("redis package is not installed", warning_mock.call_args.args[0])

    def test_allows_request_under_limit(self) -> None:
        app = FastAPI()

        @app.get("/private")
        async def private() -> dict[str, bool]:
            return {"ok": True}

        pipeline = Mock()
        pipeline.zremrangebyscore = Mock()
        pipeline.zadd = Mock()
        pipeline.zcard = Mock()
        pipeline.expire = Mock()
        pipeline.execute = AsyncMock(return_value=[None, None, 5, None])
        redis_client = Mock()
        redis_client.pipeline = Mock(return_value=pipeline)
        redis_asyncio = types.ModuleType("redis.asyncio")
        from_url = Mock(return_value=redis_client)
        setattr(redis_asyncio, "from_url", from_url)
        redis_package = types.ModuleType("redis")
        redis_package.__path__ = []
        setattr(redis_package, "asyncio", redis_asyncio)

        with patch.dict(
            sys.modules,
            {"redis": redis_package, "redis.asyncio": redis_asyncio},
            clear=False,
        ):
            setup_rate_limiting(app, "redis://localhost:6379/0", rpm=60, burst=10)
            with TestClient(app) as client:
                response = client.get("/private")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"ok": True})
        from_url.assert_called_once_with("redis://localhost:6379/0", decode_responses=True)
        redis_client.pipeline.assert_called_once_with()
        pipeline.execute.assert_awaited_once()

    def test_blocks_request_over_limit(self) -> None:
        app = FastAPI()

        @app.get("/private")
        async def private() -> dict[str, bool]:
            return {"ok": True}

        pipeline = Mock()
        pipeline.zremrangebyscore = Mock()
        pipeline.zadd = Mock()
        pipeline.zcard = Mock()
        pipeline.expire = Mock()
        pipeline.execute = AsyncMock(return_value=[None, None, 75, None])
        redis_client = Mock()
        redis_client.pipeline = Mock(return_value=pipeline)
        redis_asyncio = types.ModuleType("redis.asyncio")
        from_url = Mock(return_value=redis_client)
        setattr(redis_asyncio, "from_url", from_url)
        redis_package = types.ModuleType("redis")
        redis_package.__path__ = []
        setattr(redis_package, "asyncio", redis_asyncio)

        with patch.dict(
            sys.modules,
            {"redis": redis_package, "redis.asyncio": redis_asyncio},
            clear=False,
        ):
            setup_rate_limiting(app, "redis://localhost:6379/0", rpm=60, burst=10)
            with TestClient(app) as client:
                response = client.get("/private")

        self.assertEqual(response.status_code, 429)
        self.assertEqual(response.json()["type"], "about:blank")
        self.assertEqual(response.json()["title"], "Too Many Requests")
        self.assertEqual(response.json()["status"], 429)
        self.assertEqual(
            response.json()["detail"],
            "Rate limit exceeded: 60 requests/minute allowed.",
        )
        self.assertEqual(response.headers["Retry-After"], "60")

    def test_public_paths_exempt(self) -> None:
        app = FastAPI()

        @app.get("/health")
        async def health() -> dict[str, bool]:
            return {"ok": True}

        pipeline = Mock()
        pipeline.zremrangebyscore = Mock()
        pipeline.zadd = Mock()
        pipeline.zcard = Mock()
        pipeline.expire = Mock()
        pipeline.execute = AsyncMock(return_value=[None, None, 75, None])
        redis_client = Mock()
        redis_client.pipeline = Mock(return_value=pipeline)
        redis_asyncio = types.ModuleType("redis.asyncio")
        from_url = Mock(return_value=redis_client)
        setattr(redis_asyncio, "from_url", from_url)
        redis_package = types.ModuleType("redis")
        redis_package.__path__ = []
        setattr(redis_package, "asyncio", redis_asyncio)

        with patch.dict(
            sys.modules,
            {"redis": redis_package, "redis.asyncio": redis_asyncio},
            clear=False,
        ):
            setup_rate_limiting(app, "redis://localhost:6379/0", rpm=60, burst=10)
            with TestClient(app) as client:
                response = client.get("/health")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"ok": True})
        redis_client.pipeline.assert_not_called()

    def test_fails_open_on_redis_error(self) -> None:
        app = FastAPI()

        @app.get("/private")
        async def private() -> dict[str, bool]:
            return {"ok": True}

        pipeline = Mock()
        pipeline.zremrangebyscore = Mock()
        pipeline.zadd = Mock()
        pipeline.zcard = Mock()
        pipeline.expire = Mock()
        pipeline.execute = AsyncMock(side_effect=RuntimeError("redis unavailable"))
        redis_client = Mock()
        redis_client.pipeline = Mock(return_value=pipeline)
        redis_asyncio = types.ModuleType("redis.asyncio")
        from_url = Mock(return_value=redis_client)
        setattr(redis_asyncio, "from_url", from_url)
        redis_package = types.ModuleType("redis")
        redis_package.__path__ = []
        setattr(redis_package, "asyncio", redis_asyncio)

        with patch.dict(
            sys.modules,
            {"redis": redis_package, "redis.asyncio": redis_asyncio},
            clear=False,
        ):
            setup_rate_limiting(app, "redis://localhost:6379/0", rpm=60, burst=10)
            with TestClient(app) as client:
                response = client.get("/private")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"ok": True})
        pipeline.execute.assert_awaited_once()
