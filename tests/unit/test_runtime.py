import os
import signal
import sys
import threading
import time

import pytest

from pipeline.health import main as health_main
from pipeline.runtime import StopFlag, heartbeat_fresh, touch_heartbeat


def _install(flag: StopFlag) -> dict[int, signal.Handlers]:
    previous = {
        signal.SIGTERM: signal.getsignal(signal.SIGTERM),
        signal.SIGINT: signal.getsignal(signal.SIGINT),
    }
    flag.install()
    return previous


def _restore(previous: dict[int, signal.Handlers]) -> None:
    for signum, handler in previous.items():
        signal.signal(signum, handler)


def test_sigterm_sets_stop_flag():
    flag = StopFlag()
    previous = _install(flag)
    try:
        signal.raise_signal(signal.SIGTERM)
        assert flag.is_set()
    finally:
        _restore(previous)


def test_sigint_sets_stop_flag():
    flag = StopFlag()
    previous = _install(flag)
    try:
        signal.raise_signal(signal.SIGINT)
        assert flag.is_set()
    finally:
        _restore(previous)


def test_sigterm_wakes_wait():
    flag = StopFlag()
    previous = _install(flag)
    timer = threading.Timer(0.15, lambda: os.kill(os.getpid(), signal.SIGTERM))
    timer.daemon = True
    timer.start()
    try:
        started = time.monotonic()
        assert flag.wait(5) is True
        assert time.monotonic() - started < 2
    finally:
        timer.cancel()
        _restore(previous)


def test_fresh_heartbeat_passes_and_stale_fails(tmp_path):
    path = touch_heartbeat(tmp_path, "simulator")
    assert heartbeat_fresh(path, 45)
    stale_at = path.stat().st_mtime + 120
    assert heartbeat_fresh(path, 45, now=stale_at) is False


def test_missing_heartbeat_fails(tmp_path):
    assert heartbeat_fresh(tmp_path / ".heartbeats" / "infer", 45) is False


def test_health_command_exit_codes(tmp_path, monkeypatch):
    monkeypatch.setenv("DASHBITE_DATA_ROOT", str(tmp_path))
    monkeypatch.setenv("HEARTBEAT_MAX_AGE_SECONDS", "45")
    monkeypatch.setattr(sys, "argv", ["pipeline.health", "simulator"])

    with pytest.raises(SystemExit) as missing:
        health_main()
    assert missing.value.code == 1

    touch_heartbeat(tmp_path, "simulator")
    assert health_main() is None

    path = tmp_path / ".heartbeats" / "simulator"
    stale = time.time() - 120
    os.utime(path, (stale, stale))
    with pytest.raises(SystemExit) as aged:
        health_main()
    assert aged.value.code == 1
