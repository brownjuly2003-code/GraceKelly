from __future__ import annotations

from threading import Lock


class ModelConcurrencyGate:
    def __init__(self) -> None:
        self._lock = Lock()
        self._active_counts: dict[str, int] = {}

    def try_acquire(self, model_id: str, *, limit: int) -> bool:
        if limit < 1:
            raise ValueError("Concurrency limit must be at least 1.")
        with self._lock:
            active = self._active_counts.get(model_id, 0)
            if active >= limit:
                return False
            self._active_counts[model_id] = active + 1
            return True

    def release(self, model_id: str) -> None:
        with self._lock:
            active = self._active_counts.get(model_id, 0)
            if active < 1:
                raise RuntimeError(
                    f"Attempted to release concurrency slot for '{model_id}' with no active execution."
                )
            if active == 1:
                self._active_counts.pop(model_id, None)
                return
            self._active_counts[model_id] = active - 1

    def snapshot(self) -> dict[str, int]:
        with self._lock:
            return dict(self._active_counts)
