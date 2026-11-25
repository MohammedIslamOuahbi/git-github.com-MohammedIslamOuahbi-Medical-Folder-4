from __future__ import annotations

import threading
from datetime import datetime, timezone


class MaintenanceModeState:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._enabled = False
        self._stage = "idle"
        self._message = "Aucune operation de maintenance."
        self._started_at: datetime | None = None

    def enable(self, *, stage: str, message: str) -> None:
        with self._lock:
            self._enabled = True
            self._stage = stage
            self._message = message
            self._started_at = datetime.now(timezone.utc)

    def disable(self) -> None:
        with self._lock:
            self._enabled = False
            self._stage = "idle"
            self._message = "Aucune operation de maintenance."
            self._started_at = None

    def update(self, *, stage: str, message: str) -> None:
        with self._lock:
            self._stage = stage
            self._message = message
            if self._started_at is None:
                self._started_at = datetime.now(timezone.utc)

    def snapshot(self) -> dict[str, object]:
        with self._lock:
            return {
                "enabled": self._enabled,
                "stage": self._stage,
                "message": self._message,
                "started_at": self._started_at,
            }


maintenance_mode_state = MaintenanceModeState()
