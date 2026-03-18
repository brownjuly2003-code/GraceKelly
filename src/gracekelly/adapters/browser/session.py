from __future__ import annotations

from dataclasses import dataclass, replace
import logging
from threading import Lock

logger = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class BrowserSessionConfig:
    enabled: bool
    provider: str
    base_url: str
    profile_dir: str | None = None


@dataclass(slots=True)
class BrowserSessionState:
    configured: bool
    active: bool
    provider: str
    base_url: str
    profile_dir: str | None = None
    last_error: str | None = None


class BrowserSessionManager:
    def __init__(self, config: BrowserSessionConfig) -> None:
        self._config = config
        self._lock = Lock()
        self._state = BrowserSessionState(
            configured=bool(config.enabled and config.profile_dir),
            active=False,
            provider=config.provider,
            base_url=config.base_url,
            profile_dir=config.profile_dir,
            last_error=None if config.enabled else "Browser adapter is disabled.",
        )

    @property
    def state(self) -> BrowserSessionState:
        with self._lock:
            return replace(self._state)

    def is_ready(self) -> bool:
        with self._lock:
            return self._state.configured and self._state.active

    def mark_active(self) -> None:
        with self._lock:
            self._state.active = True
            self._state.last_error = None
            provider = self._state.provider
        logger.info("Browser session marked active for provider %s", provider)

    def mark_error(self, message: str) -> None:
        with self._lock:
            self._state.active = False
            self._state.last_error = message
            provider = self._state.provider
        logger.warning("Browser session marked degraded for provider %s: %s", provider, message)

    def mark_idle(self) -> None:
        with self._lock:
            self._state.active = False
            self._state.last_error = None
            provider = self._state.provider
        logger.info("Browser session marked idle for provider %s", provider)

    def healthcheck(self) -> dict[str, object]:
        state = self.state
        status = "ok" if state.configured and state.active else "degraded"
        return {
            "status": status,
            "provider": state.provider,
            "configured": state.configured,
            "active": state.active,
            "base_url": state.base_url,
            "profile_dir": state.profile_dir,
            "last_error": state.last_error,
        }
