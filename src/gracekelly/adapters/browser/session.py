from __future__ import annotations

from dataclasses import dataclass


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
        return self._state

    def is_ready(self) -> bool:
        return self._state.configured and self._state.active

    def mark_active(self) -> None:
        self._state.active = True
        self._state.last_error = None

    def mark_error(self, message: str) -> None:
        self._state.active = False
        self._state.last_error = message

    def healthcheck(self) -> dict[str, object]:
        status = "ok" if self.is_ready() else "degraded"
        return {
            "status": status,
            "provider": self._state.provider,
            "configured": self._state.configured,
            "active": self._state.active,
            "base_url": self._state.base_url,
            "profile_dir": self._state.profile_dir,
            "last_error": self._state.last_error,
        }
