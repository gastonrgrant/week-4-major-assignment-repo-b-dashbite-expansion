from pipeline.files import read_rows, write_rows
from pipeline.preprocess import FEATURE_COLUMNS, clean_row, process_file
from pipeline.simulator import RAW_COLUMNS


def _raw(**overrides):
    row = {
        "order_id": "abc",
        "timestamp": "2026-09-27T12:15:00",
        "distance_km": "3.5",
        "prep_minutes": "12",
        "order_value": "20.0",
        "was_late": "1",
    }
    row.update(overrides)
    return row


def test_hour_and_peak_from_timestamp():
    lunch = clean_row(_raw(timestamp="2026-09-27T12:15:00"))
    morning = clean_row(_raw(timestamp="2026-09-27T08:00:00"))
    dinner = clean_row(_raw(timestamp="2026-09-27T18:05:00"))
    assert lunch["hour"] == 12 and lunch["is_peak"] == 1
    assert morning["hour"] == 8 and morning["is_peak"] == 0
    assert dinner["is_peak"] == 1


def test_peak_hour_edges():
    off_peak = (10, 14, 16, 21)
    peak = (11, 13, 17, 20)
    for hour in off_peak:
        row = clean_row(_raw(timestamp=f"2026-09-27T{hour:02d}:00:00"))
        assert row["is_peak"] == 0
    for hour in peak:
        row = clean_row(_raw(timestamp=f"2026-09-27T{hour:02d}:00:00"))
        assert row["is_peak"] == 1


def test_drops_blank_distance_and_bad_label():
    assert clean_row(_raw(distance_km="")) is None
    assert clean_row(_raw(was_late="maybe")) is None


def test_process_file_keeps_valid_rows(tmp_path):
    source = tmp_path / "orders.csv"
    dest = tmp_path / "features.csv"
    write_rows(
        source,
        RAW_COLUMNS,
        [_raw(), _raw(order_id="bad", distance_km="n/a"), _raw(order_id="night", timestamp="2026-09-27T08:00:00")],
    )
    kept = process_file(source, dest)
    rows = read_rows(dest)
    assert kept == 2
    assert list(rows[0]) == FEATURE_COLUMNS
    assert rows[0]["was_late"] == "1"
    assert "hour" in rows[0] and "is_peak" in rows[0]
