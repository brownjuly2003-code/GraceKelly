from __future__ import annotations

import logging
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from threading import Lock

logger = logging.getLogger(__name__)


@dataclass(slots=True)
class Account:
    id: str
    credential: str
    provider: str
    kind: str  # "api_key" or "browser_profile"
    busy: bool = False
    cooldown_until: datetime | None = None
    last_used_at: datetime | None = None
    total_uses: int = 0
    total_failures: int = 0


@dataclass(frozen=True, slots=True)
class AccountPoolConfig:
    default_cooldown_seconds: float = 60.0


class AccountPool:
    def __init__(
        self,
        accounts: list[Account] | None = None,
        *,
        config: AccountPoolConfig | None = None,
        now_factory: Callable[[], datetime] | None = None,
    ) -> None:
        self._accounts: list[Account] = list(accounts or [])
        self._config = config or AccountPoolConfig()
        self._now_factory = now_factory or (lambda: datetime.now(UTC))
        self._lock = Lock()

    def add(self, account: Account) -> None:
        with self._lock:
            if any(a.id == account.id for a in self._accounts):
                raise ValueError(f"Duplicate account id: {account.id}")
            self._accounts.append(account)
            logger.info(
                "Account added id=%s provider=%s kind=%s",
                account.id,
                account.provider,
                account.kind,
            )

    def acquire(self, provider: str, kind: str | None = None) -> Account | None:
        now = self._now_factory()
        with self._lock:
            best: Account | None = None
            for account in self._accounts:
                if account.provider != provider:
                    continue
                if kind is not None and account.kind != kind:
                    continue
                if account.busy:
                    continue
                if account.cooldown_until is not None and now < account.cooldown_until:
                    continue
                if best is None or (account.last_used_at or datetime.min.replace(tzinfo=UTC)) < (best.last_used_at or datetime.min.replace(tzinfo=UTC)):
                    best = account
            if best is None:
                return None
            best.busy = True
            best.last_used_at = now
            best.total_uses += 1
            logger.debug(
                "Account acquired id=%s provider=%s uses=%d",
                best.id,
                best.provider,
                best.total_uses,
            )
            return best

    def release(self, account_id: str) -> None:
        with self._lock:
            account = self._find(account_id)
            if account is not None:
                account.busy = False

    def mark_cooldown(
        self,
        account_id: str,
        seconds: float | None = None,
    ) -> None:
        cooldown = seconds if seconds is not None else self._config.default_cooldown_seconds
        now = self._now_factory()
        with self._lock:
            account = self._find(account_id)
            if account is not None:
                account.busy = False
                account.cooldown_until = now + timedelta(seconds=cooldown)
                account.total_failures += 1
                logger.info(
                    "Account cooldown id=%s provider=%s until=%s failures=%d",
                    account.id,
                    account.provider,
                    account.cooldown_until.isoformat(),
                    account.total_failures,
                )

    def available_count(self, provider: str, kind: str | None = None) -> int:
        now = self._now_factory()
        with self._lock:
            count = 0
            for account in self._accounts:
                if account.provider != provider:
                    continue
                if kind is not None and account.kind != kind:
                    continue
                if account.busy:
                    continue
                if account.cooldown_until is not None and now < account.cooldown_until:
                    continue
                count += 1
            return count

    def snapshot(self) -> list[dict[str, object]]:
        now = self._now_factory()
        with self._lock:
            result = []
            for account in self._accounts:
                on_cooldown = (
                    account.cooldown_until is not None
                    and now < account.cooldown_until
                )
                status = "cooldown" if on_cooldown else ("busy" if account.busy else "available")
                result.append({
                    "id": account.id,
                    "provider": account.provider,
                    "kind": account.kind,
                    "status": status,
                    "total_uses": account.total_uses,
                    "total_failures": account.total_failures,
                })
            return result

    def _find(self, account_id: str) -> Account | None:
        for account in self._accounts:
            if account.id == account_id:
                return account
        return None
