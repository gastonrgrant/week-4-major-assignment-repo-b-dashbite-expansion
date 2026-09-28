from __future__ import annotations

import os
import signal
import threading
import time
from pathlib import Path


class StopFlag:
    def __init__(self) -> None:
        self._event = threading.Event()

    def install(self) -> "StopFlag":
        def handle(signum: int, frame: object) -> None:
            self._event.set()

        signal.signal(signal.SIGTERM, handle)
        signal.signal(signal.SIGINT, handle)
        return self

    def is_set(self) -> bool:
        return self._event.is_set()

    def wait(self, seconds: float) -> bool:
        return self._event.wait(seconds)


def heartbeat_path(root: Path, name: str) -> Path:
    return root / ".heartbeats" / name


def touch_heartbeat(root: Path, name: str) -> Path:
    path = heartbeat_path(root, name)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("ok\n", encoding="utf-8")
    return path


def heartbeat_fresh(path: Path, max_age_seconds: float, now: float | None = None) -> bool:
    if not path.exists():
        return False
    current = time.time() if now is None else now
    return (current - path.stat().st_mtime) <= max_age_seconds


def heartbeat_max_age() -> float:
    raw = os.environ.get("HEARTBEAT_MAX_AGE_SECONDS", "45")
    return float(raw)
