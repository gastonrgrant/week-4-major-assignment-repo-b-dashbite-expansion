import logging
import random

from pipeline.files import read_rows
from pipeline.simulator import RAW_COLUMNS, announce_batch, build_row, write_batch


def test_clean_row_has_late_flag():
    row = build_row(random.Random(1), messy=False)
    assert list(row) == RAW_COLUMNS
    assert row["was_late"] in {"0", "1"}


def test_announce_mentions_new_orders(caplog, tmp_path):
    path = tmp_path / "orders.csv"
    with caplog.at_level(logging.INFO, logger="pipeline.simulator"):
        announce_batch(path, 50)
    assert "new orders arrived" in caplog.text


def test_write_batch_row_count(tmp_path):
    path = write_batch(tmp_path, 50, random.Random(2))
    rows = read_rows(path)
    assert len(rows) == 50
    assert list(rows[0]) == RAW_COLUMNS
