from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

from gracekelly.core.account_pool import AccountPool


@dataclass(frozen=True, slots=True)
class PooledExecutionResult:
    account_id: str
    response: str
    success: bool


class AccountPoolManager:
    def __init__(
        self,
        pool: AccountPool | None = None,
        cooldown_seconds: float = 60.0,
    ) -> None:
        self._pool = pool or AccountPool()
        self._cooldown = cooldown_seconds

    @property
    def pool(self) -> AccountPool:
        return self._pool

    def execute_with_account(
        self,
        provider: str,
        execute_fn: Callable[[str, str], str],
        prompt: str,
    ) -> PooledExecutionResult:
        account = self._pool.acquire(provider)
        if account is None:
            return PooledExecutionResult(
                account_id="",
                response="No accounts available",
                success=False,
            )
        try:
            response = execute_fn(prompt, account.credential)
            self._pool.release(account.id)
            return PooledExecutionResult(
                account_id=account.id,
                response=response,
                success=True,
            )
        except Exception:
            self._pool.mark_cooldown(account.id, self._cooldown)
            return PooledExecutionResult(
                account_id=account.id,
                response="Execution failed",
                success=False,
            )

    def available_count(self, provider: str) -> int:
        return self._pool.available_count(provider)
