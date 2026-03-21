from __future__ import annotations

import json
import os
from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class AccountCredential:
    provider: str
    account_id: str
    api_key: str


def load_accounts(json_string: str) -> list[AccountCredential]:
    try:
        data = json.loads(json_string)
    except (json.JSONDecodeError, TypeError):
        return []
    if not isinstance(data, list):
        return []
    result = []
    for item in data:
        if isinstance(item, dict) and all(
            k in item for k in ("provider", "account_id", "api_key")
        ):
            result.append(
                AccountCredential(
                    provider=str(item["provider"]),
                    account_id=str(item["account_id"]),
                    api_key=str(item["api_key"]),
                )
            )
    return result


def load_accounts_from_env(
    env_var: str = "GRACEKELLY_ACCOUNTS",
) -> list[AccountCredential]:
    raw = os.getenv(env_var, "")
    if not raw:
        return []
    return load_accounts(raw)
