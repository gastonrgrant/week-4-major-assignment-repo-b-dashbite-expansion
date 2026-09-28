from __future__ import annotations

import logging
from pathlib import Path

import joblib

from pipeline.config import configure_logging, load_config
from pipeline.files import read_rows, write_rows
from pipeline.paths import ensure_data_dirs
from pipeline.runtime import StopFlag, touch_heartbeat

PREDICTION_COLUMNS = ["order_id", "late_probability", "predicted_late", "checkpoint_id"]

logger = logging.getLogger(__name__)


def predicted_late(probability: float) -> int:
    return 1 if probability >= 0.5 else 0


def newest_checkpoint(models_dir: Path) -> Path | None:
    if not models_dir.exists():
        return None
    best_path = None
    best_number = -1
    for path in models_dir.glob("late_v*.joblib"):
        suffix = path.stem.replace("late_v", "", 1)
        if not suffix.isdigit():
            continue
        number = int(suffix)
        if number > best_number:
            best_number = number
            best_path = path
    return best_path


def score_new_files(features_dir: Path, models_dir: Path, predictions_dir: Path) -> list[Path]:
    checkpoint = newest_checkpoint(models_dir)
    if checkpoint is None:
        logger.info("waiting for checkpoint")
        return []
    model = joblib.load(checkpoint)
    class_index = list(model.classes_).index(1)
    written: list[Path] = []
    predictions_dir.mkdir(parents=True, exist_ok=True)
    if not features_dir.exists():
        return []
    for source in sorted(features_dir.glob("*.csv")):
        dest = predictions_dir / source.name
        if dest.exists():
            continue
        scored = []
        for row in read_rows(source):
            distance = row.get("distance_km", "").strip()
            prep = row.get("prep_minutes", "").strip()
            order_id = row.get("order_id", "").strip()
            if not order_id or not distance or not prep:
                continue
            probability = float(model.predict_proba([[float(distance), float(prep)]])[0][class_index])
            scored.append(
                {
                    "order_id": order_id,
                    "late_probability": f"{probability:.6f}",
                    "predicted_late": predicted_late(probability),
                    "checkpoint_id": checkpoint.stem,
                }
            )
        write_rows(dest, PREDICTION_COLUMNS, scored)
        written.append(dest)
        logger.info("predictions written: %s rows -> %s", len(scored), dest.name)
    return written


def main() -> None:
    configure_logging()
    config = load_config()
    dirs = ensure_data_dirs()
    logger.info("infer polling every %s seconds", config.poll_interval_seconds)
    stop = StopFlag().install()
    while not stop.is_set():
        score_new_files(dirs["features"], dirs["models"], dirs["predictions"])
        touch_heartbeat(dirs["raw"].parent, "infer")
        stop.wait(config.poll_interval_seconds)
    logger.info("infer stopped")


if __name__ == "__main__":
    main()
