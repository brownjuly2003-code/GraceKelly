from __future__ import annotations

import unittest
from unittest.mock import MagicMock

from gracekelly.app_state import AppState, get_app_state


class AppStateTests(unittest.TestCase):
    def test_get_app_state_returns_cast_state(self) -> None:
        request = MagicMock()
        request.app.state = object()
        result = get_app_state(request)
        self.assertIs(result, request.app.state)

    def test_app_state_attributes_assignable(self) -> None:
        state = AppState()
        state.api_adapters = {}  # type: ignore[assignment]
        self.assertEqual(state.api_adapters, {})

    def test_app_state_is_class(self) -> None:
        self.assertTrue(isinstance(AppState(), AppState))

    def test_get_app_state_uses_request_app_state(self) -> None:
        request = MagicMock()
        sentinel = object()
        request.app.state = sentinel
        self.assertIs(get_app_state(request), sentinel)


if __name__ == "__main__":
    unittest.main()
