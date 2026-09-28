from __future__ import annotations

import json
import logging
from pathlib import Path

import joblib
from sklearn.linear_model import LogisticRegression

from pipeline.config import configure_logging, load_config
from pipeline.files import read_rows
from pipeline.paths import ensure_data_dirs
from pipeline.runtime import StopFlag, touch_heartbeat

FEATURES = ["distance_km", "prep_minutes"]
CURSOR_NAME = "train_cursor.json"

logger = logging.getLogger(__name__)


def next_version_stem(models_dir: Path) -> str:
    numbers = []
    if models_dir.exists():
        for path in models_dir.glob("late_v*.joblib"):
            suffix = path.stem.replace("late_v", "", 1)
            if suffix.isdigit():
                numbers.append(int(suffix))
    return f"late_v{max(numbers, default=0) + 1:03d}"


def rows_already_published(models_dir: Path) -> int:
    total = 0
    if not models_dir.exists():
        return 0
    for path in models_dir.glob("late_v*.metrics.json"):
        payload = json.loads(path.read_text(encoding="utf-8"))
        total += int(payload["n_rows"])
    return total


def cursor_path(models_dir: Path) -> Path:
    return models_dir / CURSOR_NAME


def load_cursor(models_dir: Path) -> list[str] | None:
    path = cursor_path(models_dir)
    if not path.exists():
        return None
    payload = json.loads(path.read_text(encoding="utf-8"))
    return list(payload["files"])


def save_cursor(models_dir: Path, files: list[str]) -> None:
    models_dir.mkdir(parents=True, exist_ok=True)
    cursor_path(models_dir).write_text(
        json.dumps({"files": files}, indent=2) + "\n",
        encoding="utf-8",
    )


def _is_labeled(row: dict[str, str]) -> bool:
    return bool(row.get("distance_km") and row.get("prep_minutes") and row.get("was_late") in {"0", "1"})


def feature_files(features_dir: Path) -> list[Path]:
    if not features_dir.exists():
        return []
    return sorted(path for path in features_dir.glob("*.csv") if path.is_file())


def labeled_rows(paths: list[Path]) -> list[dict[str, str]]:
    rows = []
    for path in paths:
        for row in read_rows(path):
            if _is_labeled(row):
                rows.append(row)
    return rows


def consumed_prefix(features_dir: Path, target: int) -> list[str] | None:
    if target < 0:
        return None
    consumed: list[str] = []
    total = 0
    for path in feature_files(features_dir):
        if total == target:
            return consumed
        count = len(labeled_rows([path]))
        if total + count > target:
            return None
        total += count
        consumed.append(path.name)
    if total == target:
        return consumed
    return None


def _has_sidecars(models_dir: Path) -> bool:
    return models_dir.exists() and any(models_dir.glob("late_v*.metrics.json"))


def _ensure_cursor(features_dir: Path, models_dir: Path) -> list[str] | None:
    cursor = load_cursor(models_dir)
    if cursor is not None:
        return cursor
    if not _has_sidecars(models_dir):
        return []
    rebuilt = consumed_prefix(features_dir, rows_already_published(models_dir))
    if rebuilt is None:
        return None
    save_cursor(models_dir, rebuilt)
    return rebuilt


def _write_checkpoint(models_dir: Path, fit_rows: list[dict[str, str]], n_rows: int) -> Path:
    model = LogisticRegression(max_iter=1000)
    model.fit(
        [[float(row["distance_km"]), float(row["prep_minutes"])] for row in fit_rows],
        [int(row["was_late"]) for row in fit_rows],
    )
    models_dir.mkdir(parents=True, exist_ok=True)
    stem = next_version_stem(models_dir)
    checkpoint = models_dir / f"{stem}.joblib"
    sidecar = models_dir / f"{stem}.metrics.json"
    joblib.dump(model, checkpoint)
    coefficients = [float(value) for value in model.coef_[0]]
    sidecar.write_text(
        json.dumps(
            {
                "version": stem,
                "n_rows": n_rows,
                "n_rows_fit": len(fit_rows),
                "features": list(FEATURES),
                "coefficients": {
                    FEATURES[0]: coefficients[0],
                    FEATURES[1]: coefficients[1],
                },
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    logger.info("checkpoint published: %s", checkpoint.name)
    return checkpoint


def _publish_from_row_count(features_dir: Path, models_dir: Path, every_n: int) -> Path | None:
    rows = labeled_rows(feature_files(features_dir))
    fresh = rows[rows_already_published(models_dir) :]
    if len(fresh) < every_n:
        return None
    labels = {row["was_late"] for row in fresh}
    if labels != {"0", "1"}:
        logger.info("waiting for both late and on-time labels before publishing")
        return None
    return _write_checkpoint(models_dir, fresh, len(fresh))


def maybe_publish(features_dir: Path, models_dir: Path, every_n: int) -> Path | None:
    cursor = _ensure_cursor(features_dir, models_dir)
    if cursor is None:
        return _publish_from_row_count(features_dir, models_dir, every_n)

    files = feature_files(features_dir)
    consumed = set(cursor)
    new_files = [path for path in files if path.name not in consumed]
    new_rows = labeled_rows(new_files)
    if len(new_rows) < every_n:
        return None

    old_files = [path for path in files if path.name in consumed]
    fit_rows = labeled_rows(old_files) + new_rows
    labels = {row["was_late"] for row in fit_rows}
    if labels != {"0", "1"}:
        logger.info("waiting for both late and on-time labels before publishing")
        return None
    checkpoint = _write_checkpoint(models_dir, fit_rows, len(new_rows))
    save_cursor(models_dir, list(cursor) + [path.name for path in new_files])
    return checkpoint


def main() -> None:
    configure_logging()
    config = load_config()
    dirs = ensure_data_dirs()
    logger.info(
        "train polling every %s seconds; publish every %s labeled rows",
        config.poll_interval_seconds,
        config.train_every_n_events,
    )
    stop = StopFlag().install()
    while not stop.is_set():
        maybe_publish(dirs["features"], dirs["models"], config.train_every_n_events)
        touch_heartbeat(dirs["raw"].parent, "train")
        stop.wait(config.poll_interval_seconds)
    logger.info("train stopped")


if __name__ == "__main__":
    main()
