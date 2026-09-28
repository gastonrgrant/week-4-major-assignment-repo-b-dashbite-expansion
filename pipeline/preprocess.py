from __future__ import annotations

import logging
from datetime import datetime
from pathlib import Path

from pipeline.config import configure_logging, load_config
from pipeline.files import read_rows, write_rows
from pipeline.paths import ensure_data_dirs
from pipeline.runtime import StopFlag, touch_heartbeat

FEATURE_COLUMNS = [
    "order_id",
    "timestamp",
    "distance_km",
    "prep_minutes",
    "order_value",
    "hour",
    "is_peak",
    "was_late",
]
PEAK_HOURS = {11, 12, 13, 17, 18, 19, 20}

logger = logging.getLogger(__name__)


def parse_timestamp(value: object) -> datetime | None:
    text = "" if value is None else str(value).strip()
    if not text or text.lower() == "n/a":
        return None
    try:
        return datetime.fromisoformat(text)
    except ValueError:
        return None


def parse_float(value: object) -> float | None:
    text = "" if value is None else str(value).strip()
    if not text or text.lower() == "n/a":
        return None
    try:
        return float(text)
    except ValueError:
        return None


def parse_was_late(value: object) -> str | None:
    text = "" if value is None else str(value).strip()
    if text in {"0", "1"}:
        return text
    return None


def clean_row(row: dict[str, str]) -> dict[str, object] | None:
    timestamp = parse_timestamp(row.get("timestamp"))
    distance = parse_float(row.get("distance_km"))
    prep = parse_float(row.get("prep_minutes"))
    value = parse_float(row.get("order_value"))
    was_late = parse_was_late(row.get("was_late"))
    order_id = str(row.get("order_id", "")).strip()
    if timestamp is None or distance is None or prep is None or value is None or was_late is None:
        return None
    if not order_id:
        return None
    hour = timestamp.hour
    return {
        "order_id": order_id,
        "timestamp": timestamp.isoformat(timespec="seconds"),
        "distance_km": distance,
        "prep_minutes": prep,
        "order_value": value,
        "hour": hour,
        "is_peak": 1 if hour in PEAK_HOURS else 0,
        "was_late": was_late,
    }


def process_file(source: Path, dest: Path) -> int:
    cleaned = []
    for row in read_rows(source):
        kept = clean_row(row)
        if kept is not None:
            cleaned.append(kept)
    write_rows(dest, FEATURE_COLUMNS, cleaned)
    return len(cleaned)


def main() -> None:
    configure_logging()
    config = load_config()
    dirs = ensure_data_dirs()
    logger.info("preprocess polling every %s seconds", config.poll_interval_seconds)
    stop = StopFlag().install()
    seen: set[str] = set()
    while not stop.is_set():
        if dirs["raw"].exists():
            for path in sorted(dirs["raw"].glob("*.csv")):
                if path.stem in seen:
                    continue
                dest = dirs["features"] / path.name
                if dest.exists():
                    seen.add(path.stem)
                    continue
                kept = process_file(path, dest)
                seen.add(path.stem)
                logger.info("features written: %s rows -> %s", kept, dest.name)
        touch_heartbeat(dirs["raw"].parent, "preprocess")
        stop.wait(config.poll_interval_seconds)
    logger.info("preprocess stopped")


if __name__ == "__main__":
    main()
