from __future__ import annotations

import unittest
from unittest.mock import MagicMock

from gracekelly.storage.postgres import _PoolConnectionWithRowFactory


class PoolConnectionWithRowFactoryTests(unittest.TestCase):
    def test_enter_sets_row_factory_on_connection(self) -> None:
        mock_conn = MagicMock()
        mock_pool_ctx = MagicMock()
        mock_pool_ctx.__enter__ = MagicMock(return_value=mock_conn)
        mock_pool_ctx.__exit__ = MagicMock(return_value=False)

        row_factory = MagicMock()
        wrapper = _PoolConnectionWithRowFactory(mock_pool_ctx, row_factory)

        with wrapper as conn:
            self.assertIs(conn, mock_conn)
            self.assertEqual(mock_conn.row_factory, row_factory)

    def test_exit_delegates_to_pool_context(self) -> None:
        mock_conn = MagicMock()
        mock_pool_ctx = MagicMock()
        mock_pool_ctx.__enter__ = MagicMock(return_value=mock_conn)
        mock_pool_ctx.__exit__ = MagicMock(return_value=False)

        wrapper = _PoolConnectionWithRowFactory(mock_pool_ctx, MagicMock())

        with wrapper:
            pass

        mock_pool_ctx.__exit__.assert_called_once()

    def test_connection_available_inside_context(self) -> None:
        mock_conn = MagicMock()
        mock_pool_ctx = MagicMock()
        mock_pool_ctx.__enter__ = MagicMock(return_value=mock_conn)
        mock_pool_ctx.__exit__ = MagicMock(return_value=False)

        wrapper = _PoolConnectionWithRowFactory(mock_pool_ctx, MagicMock())

        with wrapper as conn:
            cursor = conn.cursor()
            self.assertIsNotNone(cursor)


if __name__ == "__main__":
    unittest.main()
