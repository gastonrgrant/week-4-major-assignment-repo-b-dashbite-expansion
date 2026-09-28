from pipeline.config import load_config
from pipeline.infer import PREDICTION_COLUMNS
from pipeline.preprocess import FEATURE_COLUMNS
from pipeline.pulse import build_view
from pipeline.simulator import RAW_COLUMNS


def test_classroom_defaults_stay_put(monkeypatch):
    for name in ("TRAIN_EVERY_N_EVENTS", "BATCH_SIZE", "POLL_INTERVAL_SECONDS"):
        monkeypatch.delenv(name, raising=False)
    config = load_config()
    assert config.train_every_n_events == 2000
    assert config.batch_size == 50
    assert config.poll_interval_seconds == 15
    assert "TRAIN_EVERY_N_EVENTS=2000" in str(config)
    assert "BATCH_SIZE=50" in str(config)


def test_headers_stay_put():
    assert RAW_COLUMNS == [
        "order_id",
        "timestamp",
        "distance_km",
        "prep_minutes",
        "order_value",
        "was_late",
    ]
    assert FEATURE_COLUMNS == [
        "order_id",
        "timestamp",
        "distance_km",
        "prep_minutes",
        "order_value",
        "hour",
        "is_peak",
        "was_late",
    ]
    assert PREDICTION_COLUMNS == [
        "order_id",
        "late_probability",
        "predicted_late",
        "checkpoint_id",
    ]


def test_view_model_has_three_kpis_and_human_axes(tmp_path):
    view = build_view(tmp_path / "raw", tmp_path / "features", tmp_path / "predictions")
    assert [item["label"] for item in view["kpis"]] == ["Samples", "Drop rate", "Late flag rate"]
    assert "at-risk" not in str(view).lower()
    assert "revenue" not in str(view).lower()
    assert set(view["hero"]["points"][0]) == {"Minute", "Orders"} if view["hero"]["points"] else True
