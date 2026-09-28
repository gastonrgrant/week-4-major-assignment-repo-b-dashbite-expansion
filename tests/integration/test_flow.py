import json

import joblib
from sklearn.linear_model import LogisticRegression

from pipeline.files import read_rows, write_rows
from pipeline.infer import score_new_files
from pipeline.paths import ensure_data_dirs
from pipeline.preprocess import FEATURE_COLUMNS, process_file
from pipeline.pulse import build_view
from pipeline.simulator import RAW_COLUMNS
from pipeline.train import maybe_publish


def test_ensure_dirs_and_feature_flow(tmp_path):
    dirs = ensure_data_dirs(tmp_path)
    assert all(path.is_dir() for path in dirs.values())
    source = dirs["raw"] / "orders.csv"
    write_rows(
        source,
        RAW_COLUMNS,
        [
            {
                "order_id": f"id{i}",
                "timestamp": "2026-09-27T12:00:00" if i % 2 == 0 else "nope",
                "distance_km": "4.0" if i != 1 else "",
                "prep_minutes": "15",
                "order_value": "22",
                "was_late": "1" if i % 2 == 0 else "0",
            }
            for i in range(6)
        ],
    )
    dest = dirs["features"] / source.name
    process_file(source, dest)
    rows = read_rows(dest)
    assert rows
    assert all(row["was_late"] in {"0", "1"} for row in rows)
    assert all(row["hour"] == "12" for row in rows)


def test_publish_and_score(tmp_path):
    features = tmp_path / "features"
    models = tmp_path / "models"
    predictions = tmp_path / "predictions"
    rows = []
    for i in range(12):
        late = "1" if i >= 6 else "0"
        rows.append(
            {
                "order_id": f"r{i}",
                "timestamp": f"2026-09-27T12:{i:02d}:00",
                "distance_km": "12" if late == "1" else "1",
                "prep_minutes": "40" if late == "1" else "5",
                "order_value": "20",
                "hour": "12",
                "is_peak": "1",
                "was_late": late,
            }
        )
    write_rows(features / "batch.csv", FEATURE_COLUMNS, rows)
    checkpoint = maybe_publish(features, models, every_n=10)
    assert checkpoint.name == "late_v001.joblib"
    loaded = joblib.load(checkpoint)
    assert isinstance(loaded, LogisticRegression)
    sidecar = json.loads((models / "late_v001.metrics.json").read_text(encoding="utf-8"))
    assert sidecar["n_rows"] >= 10
    assert sidecar["n_rows_fit"] == sidecar["n_rows"]
    written = score_new_files(features, models, predictions)
    assert written
    again = score_new_files(features, models, predictions)
    assert again == []
    view = build_view(tmp_path / "raw", features, predictions)
    assert view["kpis"][0]["label"] == "Samples"
    assert view["flags"]["points"]
    assert view["checkpoint_id"] == "late_v001"
