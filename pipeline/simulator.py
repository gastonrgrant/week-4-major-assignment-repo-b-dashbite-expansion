from __future__ import annotations

import logging
import math
import random
import uuid
from datetime import datetime
from pathlib import Path

from pipeline.config import configure_logging, load_config
from pipeline.files import write_rows
from pipeline.paths import ensure_data_dirs
from pipeline.runtime import StopFlag, touch_heartbeat

RAW_COLUMNS = [
    "order_id",
    "timestamp",
    "distance_km",
    "prep_minutes",
    "order_value",
    "was_late",
]
MESSY_RATE = 0.15

logger = logging.getLogger(__name__)


def announce_batch(path: Path, n_rows: int) -> None:
    logger.info("new orders arrived: %s rows -> %s", n_rows, path.name)


def _late_probability(distance_km: float, prep_minutes: float) -> float:
    logit = 0.45 * distance_km + 0.06 * prep_minutes - 5.0
    return 1.0 / (1.0 + math.exp(-logit))


def build_row(rng: random.Random, messy: bool) -> dict[str, str]:
    distance = round(rng.uniform(0.4, 12.0), 2)
    prep = rng.randint(5, 45)
    value = round(rng.uniform(8.0, 75.0), 2)
    was_late = "1" if rng.random() < _late_probability(distance, prep) else "0"
    timestamp = datetime.now().astimezone().isoformat(timespec="seconds")
    row = {
        "order_id": uuid.uuid4().hex[:12],
        "timestamp": timestamp,
        "distance_km": f"{distance:.2f}",
        "prep_minutes": str(prep),
        "order_value": f"{value:.2f}",
        "was_late": was_late,
    }
    if messy:
        field = rng.choice(RAW_COLUMNS[1:])
        row[field] = rng.choice(["", "n/a"])
    return row


def write_batch(directory: Path, batch_size: int, rng: random.Random | None = None) -> Path:
    generator = rng or random.Random()
    rows = [
        build_row(generator, messy=generator.random() < MESSY_RATE) for _ in range(batch_size)
    ]
    stamp = datetime.now().astimezone().strftime("%Y%m%dT%H%M%S")
    path = directory / f"orders-{stamp}-{uuid.uuid4().hex[:8]}.csv"
    write_rows(path, RAW_COLUMNS, rows)
    announce_batch(path, len(rows))
    return path


def main() -> None:
    configure_logging()
    config = load_config()
    raw_dir = ensure_data_dirs()["raw"]
    logger.info("simulator polling every %s seconds", config.poll_interval_seconds)
    stop = StopFlag().install()
    while not stop.is_set():
        write_batch(raw_dir, config.batch_size)
        touch_heartbeat(raw_dir.parent, "simulator")
        stop.wait(config.poll_interval_seconds)
    logger.info("simulator stopped")


if __name__ == "__main__":
    main()
