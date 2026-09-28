import logging

import joblib
from sklearn.linear_model import LogisticRegression

from pipeline.files import read_rows, write_rows
from pipeline.infer import PREDICTION_COLUMNS, newest_checkpoint, predicted_late, score_new_files
from pipeline.preprocess import FEATURE_COLUMNS


def test_predicted_late_threshold():
    assert predicted_late(0.5) == 1
    assert predicted_late(0.49) == 0


def test_newest_checkpoint_picks_highest_version(tmp_path):
    (tmp_path / "late_v001.joblib").write_bytes(b"")
    (tmp_path / "late_v003.joblib").write_bytes(b"")
    assert newest_checkpoint(tmp_path).name == "late_v003.joblib"


def test_empty_models_writes_nothing(tmp_path, caplog):
    features = tmp_path / "features"
    models = tmp_path / "models"
    predictions = tmp_path / "predictions"
    features.mkdir()
    models.mkdir()
    write_rows(
        features / "batch.csv",
        FEATURE_COLUMNS,
        [{
            "order_id": "a",
            "timestamp": "2026-09-27T12:00:00",
            "distance_km": "2",
            "prep_minutes": "10",
            "order_value": "15",
            "hour": "12",
            "is_peak": "1",
            "was_late": "0",
        }],
    )
    with caplog.at_level(logging.INFO, logger="pipeline.infer"):
        written = score_new_files(features, models, predictions)
    assert written == []
    assert list(predictions.glob("*.csv")) == []
    assert "waiting for checkpoint" in caplog.text


def test_score_file_round_trip(tmp_path):
    features = tmp_path / "features"
    models = tmp_path / "models"
    predictions = tmp_path / "predictions"
    features.mkdir()
    models.mkdir()
    model = LogisticRegression(max_iter=200)
    model.fit([[1, 5], [2, 6], [11, 40], [12, 42]], [0, 0, 1, 1])
    joblib.dump(model, models / "late_v001.joblib")
    write_rows(
        features / "batch.csv",
        FEATURE_COLUMNS,
        [
            {
                "order_id": "near",
                "timestamp": "2026-09-27T12:00:00",
                "distance_km": "1",
                "prep_minutes": "5",
                "order_value": "10",
                "hour": "12",
                "is_peak": "1",
                "was_late": "0",
            },
            {
                "order_id": "far",
                "timestamp": "2026-09-27T12:01:00",
                "distance_km": "12",
                "prep_minutes": "40",
                "order_value": "30",
                "hour": "12",
                "is_peak": "1",
                "was_late": "1",
            },
        ],
    )
    first = score_new_files(features, models, predictions)
    second = score_new_files(features, models, predictions)
    assert len(first) == 1
    assert second == []
    rows = read_rows(predictions / "batch.csv")
    assert list(rows[0]) == PREDICTION_COLUMNS
    assert rows[0]["checkpoint_id"] == "late_v001"
    assert {row["order_id"] for row in rows} == {"near", "far"}
