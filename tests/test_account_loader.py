from __future__ import annotations

import json
import os
import unittest

from gracekelly.core.account_loader import (
    AccountCredential,
    load_accounts,
    load_accounts_from_env,
)


class TestLoadAccounts(unittest.TestCase):
    def test_valid_json_two_accounts(self) -> None:
        data = [
            {"provider": "openai", "account_id": "a1", "api_key": "k1"},
            {"provider": "anthropic", "account_id": "a2", "api_key": "k2"},
        ]
        result = load_accounts(json.dumps(data))
        self.assertEqual(len(result), 2)
        self.assertEqual(result[0], AccountCredential("openai", "a1", "k1"))
        self.assertEqual(result[1], AccountCredential("anthropic", "a2", "k2"))

    def test_empty_string(self) -> None:
        self.assertEqual(load_accounts(""), [])

    def test_invalid_json(self) -> None:
        self.assertEqual(load_accounts("{not valid json"), [])

    def test_none_input(self) -> None:
        self.assertEqual(load_accounts(None), [])

    def test_missing_fields_skipped(self) -> None:
        data = [
            {"provider": "openai", "account_id": "a1"},
            {"provider": "anthropic", "account_id": "a2", "api_key": "k2"},
        ]
        result = load_accounts(json.dumps(data))
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0].provider, "anthropic")

    def test_not_a_list(self) -> None:
        self.assertEqual(load_accounts(json.dumps({"provider": "x"})), [])

    def test_mixed_valid_invalid(self) -> None:
        data = [
            {"provider": "openai", "account_id": "a1", "api_key": "k1"},
            "not a dict",
            42,
            {"provider": "anthropic", "account_id": "a2", "api_key": "k2"},
            {"missing": "fields"},
        ]
        result = load_accounts(json.dumps(data))
        self.assertEqual(len(result), 2)
        self.assertEqual(result[0].account_id, "a1")
        self.assertEqual(result[1].account_id, "a2")

    def test_values_coerced_to_string(self) -> None:
        data = [{"provider": 123, "account_id": 456, "api_key": 789}]
        result = load_accounts(json.dumps(data))
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0].provider, "123")

    def test_empty_list(self) -> None:
        self.assertEqual(load_accounts("[]"), [])


class TestLoadAccountsFromEnv(unittest.TestCase):
    def test_with_set_env_var(self) -> None:
        data = [{"provider": "openai", "account_id": "a1", "api_key": "k1"}]
        env_var = "TEST_GRACEKELLY_ACCOUNTS_SET"
        os.environ[env_var] = json.dumps(data)
        try:
            result = load_accounts_from_env(env_var)
            self.assertEqual(len(result), 1)
            self.assertEqual(result[0].provider, "openai")
        finally:
            del os.environ[env_var]

    def test_with_unset_env_var(self) -> None:
        env_var = "TEST_GRACEKELLY_ACCOUNTS_UNSET"
        os.environ.pop(env_var, None)
        result = load_accounts_from_env(env_var)
        self.assertEqual(result, [])

    def test_with_empty_env_var(self) -> None:
        env_var = "TEST_GRACEKELLY_ACCOUNTS_EMPTY"
        os.environ[env_var] = ""
        try:
            result = load_accounts_from_env(env_var)
            self.assertEqual(result, [])
        finally:
            del os.environ[env_var]


if __name__ == "__main__":
    unittest.main()
