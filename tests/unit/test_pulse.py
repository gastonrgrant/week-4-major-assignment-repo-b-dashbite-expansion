from pipeline.files import write_rows
from pipeline.infer import PREDICTION_COLUMNS
from pipeline.preprocess import FEATURE_COLUMNS
from pipeline.pulse import build_view, field_errors, flag_title, volume_title
from pipeline.simulator import RAW_COLUMNS


def test_volume_and_flag_titles():
    assert volume_title(5, 1) == "Orders picked up over the last hour"
    assert volume_title(1, 5) == "Orders slowed over the last hour"
    assert volume_title(2, 2) == "Orders held steady over the last hour"
    assert flag_title(10, 40) == "Flagging more orders late"
    assert flag_title(40, 10) == "Flagging fewer orders late"
    assert flag_title(10, 10) == "Late flags held steady"


def test_field_errors_sorted_by_count_via_view(tmp_path):
    raw = tmp_path / "raw"
    features = tmp_path / "features"
    predictions = tmp_path / "predictions"
    write_rows(
        raw / "orders.csv",
        RAW_COLUMNS,
        [
            {
                "order_id": "1",
                "timestamp": "2026-09-27T12:00:00",
                "distance_km": "",
                "prep_minutes": "10",
                "order_value": "12",
                "was_late": "0",
            },
            {
                "order_id": "2",
                "timestamp": "2026-09-27T12:01:00",
                "distance_km": "n/a",
                "prep_minutes": "",
                "order_value": "12",
                "was_late": "1",
            },
        ],
    )
    write_rows(
        features / "orders.csv",
        FEATURE_COLUMNS,
        [
            {
                "order_id": "3",
                "timestamp": "2026-09-27T12:02:00",
                "distance_km": "2",
                "prep_minutes": "8",
                "order_value": "15",
                "hour": "12",
                "is_peak": "1",
                "was_late": "0",
            },
            {
                "order_id": "4",
                "timestamp": "2026-09-27T12:20:00",
                "distance_km": "11",
                "prep_minutes": "30",
                "order_value": "40",
                "hour": "12",
                "is_peak": "1",
                "was_late": "1",
            },
        ],
    )
    write_rows(
        predictions / "orders.csv",
        PREDICTION_COLUMNS,
        [
            {"order_id": "3", "late_probability": "0.2", "predicted_late": "0", "checkpoint_id": "late_v001"},
            {"order_id": "4", "late_probability": "0.8", "predicted_late": "1", "checkpoint_id": "late_v001"},
        ],
    )
    view = build_view(raw, features, predictions)
    assert [item["label"] for item in view["kpis"]] == ["Samples", "Drop rate", "Late flag rate"]
    assert view["hero"]["points"][0]["Orders"] >= 1
    assert view["flags"]["points"]
    assert view["failures"]["bars"][0]["label"] == "Distance"
    assert view["failures"]["bars"] == sorted(view["failures"]["bars"], key=lambda item: -item["count"])
    assert view["checkpoint_id"] == "late_v001"
    assert field_errors({"timestamp": "", "distance_km": "1", "prep_minutes": "1", "order_value": "1", "was_late": "0"}) == ["timestamp"]
