from __future__ import annotations

from collections import deque
from threading import Lock
from time import monotonic


class RequestBudget:
    def __init__(self, *, inference_per_minute: int = 30,
                 writes_per_minute: int = 180) -> None:
        if type(inference_per_minute) is not int or not 1 <= inference_per_minute <= 6000:
            raise ValueError("Inference request budget must be 1–6000 per minute")
        if type(writes_per_minute) is not int or not 1 <= writes_per_minute <= 12000:
            raise ValueError("Write request budget must be 1–12000 per minute")
        self._maximum = {"inference": inference_per_minute, "write": writes_per_minute}
        self._recent: dict[str, deque[float]] = {
            "inference": deque(),
            "write": deque(),
        }
        self._lock = Lock()

    def admit(self, kind: str, *, now: float | None = None) -> bool:
        if kind not in self._maximum:
            raise ValueError("Unknown request budget")
        current = monotonic() if now is None else now
        with self._lock:
            observations = self._recent[kind]
            while observations and observations[0] <= current - 60:
                observations.popleft()
            if len(observations) >= self._maximum[kind]:
                return False
            observations.append(current)
            return True
