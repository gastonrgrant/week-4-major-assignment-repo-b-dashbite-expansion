import json

from pipeline.files import write_rows
from pipeline.preprocess import FEATURE_COLUMNS
from pipeline.train import FEATURES, maybe_publish, next_version_stem


def _feature(order_id, distance, prep, was_late):
    return {
        "order_id": order_id,
        "timestamp": "2026-09-27T12:00:00",
        "distance_km": str(distance),
        "prep_minutes": str(prep),
        "order_value": "10",
        "hour": "12",
        "is_peak": "1",
        "was_late": was_late,
    }


def _write_labeled(directory, count, late):
    rows = [
        _feature(f"o{late}{i}", 1 if late == "0" else 12, 5 if late == "0" else 40, late)
        for i in range(count)
    ]
    write_rows(directory / f"part-{late}-{count}.csv", FEATURE_COLUMNS, rows)


def test_one_class_does_not_publish(tmp_path):
    features = tmp_path / "features"
    models = tmp_path / "models"
    _write_labeled(features, 12, "0")
    assert maybe_publish(features, models, every_n=10) is None
    assert not models.exists() or list(models.glob("late_v*.joblib")) == []
    assert not (models / "train_cursor.json").exists()


def test_below_threshold_writes_nothing(tmp_path):
    features = tmp_path / "features"
    models = tmp_path / "models"
    _write_labeled(features, 3, "0")
    _write_labeled(features, 3, "1")
    assert maybe_publish(features, models, every_n=20) is None
    assert not models.exists() or list(models.glob("*.joblib")) == []
    assert not (models / "train_cursor.json").exists()


def test_sidecar_lists_two_features_and_coefficients(tmp_path):
    features = tmp_path / "features"
    models = tmp_path / "models"
    _write_labeled(features, 8, "0")
    _write_labeled(features, 8, "1")
    checkpoint = maybe_publish(features, models, every_n=10)
    assert checkpoint.name == "late_v001.joblib"
    import json

    sidecar = json.loads((models / "late_v001.metrics.json").read_text(encoding="utf-8"))
    assert sidecar["features"] == FEATURES
    assert set(sidecar["coefficients"]) == {"distance_km", "prep_minutes"}
    assert sidecar["n_rows"] == 16
    assert sidecar["n_rows_fit"] == 16


def test_versions_do_not_overwrite(tmp_path):
    features = tmp_path / "features"
    models = tmp_path / "models"
    models.mkdir()
    (models / "late_v001.joblib").write_bytes(b"")
    (models / "late_v003.joblib").write_bytes(b"")
    assert next_version_stem(models) == "late_v004"


def test_too_few_new_rows_do_not_publish(tmp_path):
    features = tmp_path / "features"
    models = tmp_path / "models"
    _write_labeled(features, 6, "0")
    _write_labeled(features, 6, "1")
    assert maybe_publish(features, models, every_n=10) is not None
    _write_labeled(features, 2, "0")
    assert maybe_publish(features, models, every_n=10) is None
    assert list(models.glob("*.joblib")) == [models / "late_v001.joblib"]


def test_second_publish_fits_old_rows_and_new_rows(tmp_path):
    features = tmp_path / "features"
    models = tmp_path / "models"
    _write_labeled(features, 6, "0")
    _write_labeled(features, 6, "1")
    assert maybe_publish(features, models, every_n=10) is not None
    _write_labeled(features, 8, "0")
    _write_labeled(features, 4, "1")
    checkpoint = maybe_publish(features, models, every_n=10)
    assert checkpoint.name == "late_v002.joblib"
    sidecar = json.loads((models / "late_v002.metrics.json").read_text(encoding="utf-8"))
    assert sidecar["n_rows"] == 12
    assert sidecar["n_rows_fit"] == 24
    cursor = json.loads((models / "train_cursor.json").read_text(encoding="utf-8"))
    assert set(cursor["files"]) == {
        "part-0-6.csv",
        "part-1-6.csv",
        "part-0-8.csv",
        "part-1-4.csv",
    }


def test_on_time_batch_publishes_when_history_has_both_labels(tmp_path):
    features = tmp_path / "features"
    models = tmp_path / "models"
    _write_labeled(features, 6, "0")
    _write_labeled(features, 6, "1")
    assert maybe_publish(features, models, every_n=10) is not None
    _write_labeled(features, 12, "0")
    checkpoint = maybe_publish(features, models, every_n=10)
    assert checkpoint.name == "late_v002.joblib"


def _write_named(directory, name, count, late):
    rows = [
        _feature(f"{name}-{i}", 1 if late == "0" else 12, 5 if late == "0" else 40, late)
        for i in range(count)
    ]
    write_rows(directory / name, FEATURE_COLUMNS, rows)


def test_missing_cursor_rebuilds_on_file_boundary(tmp_path):
    features = tmp_path / "features"
    models = tmp_path / "models"
    models.mkdir()
    _write_named(features, "a-old.csv", 6, "0")
    _write_named(features, "b-old.csv", 6, "1")
    _write_named(features, "c-new.csv", 4, "0")
    (models / "late_v001.metrics.json").write_text(
        json.dumps({"version": "late_v001", "n_rows": 12}) + "\n",
        encoding="utf-8",
    )
    assert maybe_publish(features, models, every_n=10) is None
    cursor = json.loads((models / "train_cursor.json").read_text(encoding="utf-8"))
    assert cursor["files"] == ["a-old.csv", "b-old.csv"]
    assert list(models.glob("*.joblib")) == []


def test_split_file_does_not_guess_a_cursor(tmp_path):
    features = tmp_path / "features"
    models = tmp_path / "models"
    models.mkdir()
    _write_named(features, "only.csv", 10, "0")
    (models / "late_v001.metrics.json").write_text(
        json.dumps({"version": "late_v001", "n_rows": 4}) + "\n",
        encoding="utf-8",
    )
    assert maybe_publish(features, models, every_n=100) is None
    assert not (models / "train_cursor.json").exists()
