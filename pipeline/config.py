from __future__ import annotations

import logging
import os
from dataclasses import dataclass


@dataclass(frozen=True)
class Config:
    train_every_n_events: int
    batch_size: int
    poll_interval_seconds: int

    def __str__(self) -> str:
        return (
            f"TRAIN_EVERY_N_EVENTS={self.train_every_n_events} "
            f"BATCH_SIZE={self.batch_size} "
            f"POLL_INTERVAL_SECONDS={self.poll_interval_seconds}"
        )


def _int_env(name: str, default: int) -> int:
    raw = os.environ.get(name)
    if raw is None or raw.strip() == "":
        return default
    return int(raw)


def load_config() -> Config:
    return Config(
        train_every_n_events=_int_env("TRAIN_EVERY_N_EVENTS", 2000),
        batch_size=_int_env("BATCH_SIZE", 50),
        poll_interval_seconds=_int_env("POLL_INTERVAL_SECONDS", 15),
    )


def configure_logging() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s", force=True)
