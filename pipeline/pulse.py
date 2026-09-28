from __future__ import annotations

from datetime import datetime, timedelta
from pathlib import Path

from pipeline.files import read_dir

WINDOW = timedelta(minutes=60)
RECENT = timedelta(minutes=15)
FIELD_LABELS = {
    "timestamp": "Timestamp",
    "distance_km": "Distance",
    "prep_minutes": "Prep time",
    "order_value": "Order value",
    "was_late": "Late label",
}


def parse_timestamp(value: object) -> datetime | None:
    text = "" if value is None else str(value).strip()
    if not text or text.lower() == "n/a":
        return None
    try:
        return datetime.fromisoformat(text)
    except ValueError:
        return None


def _blank_or_non_numeric(value: object) -> bool:
    text = "" if value is None else str(value).strip()
    if not text or text.lower() == "n/a":
        return True
    try:
        float(text)
    except ValueError:
        return True
    return False


def field_errors(row: dict[str, str]) -> list[str]:
    errors = []
    if parse_timestamp(row.get("timestamp")) is None:
        errors.append("timestamp")
    for column in ("distance_km", "prep_minutes", "order_value"):
        if _blank_or_non_numeric(row.get(column)):
            errors.append(column)
    late = "" if row.get("was_late") is None else str(row.get("was_late")).strip()
    if late not in {"0", "1"}:
        errors.append("was_late")
    return errors


def volume_title(recent: int, prior: int) -> str:
    if recent > prior:
        return "Orders picked up over the last hour"
    if recent < prior:
        return "Orders slowed over the last hour"
    return "Orders held steady over the last hour"


def flag_title(earlier: float, later: float) -> str:
    if later > earlier:
        return "Flagging more orders late"
    if later < earlier:
        return "Flagging fewer orders late"
    return "Late flags held steady"


def _minute(timestamp: datetime) -> datetime:
    return timestamp.replace(second=0, microsecond=0)


def _in_window(timestamp: datetime | None, start: datetime | None, end: datetime | None) -> bool:
    if timestamp is None or start is None or end is None:
        return False
    return start < timestamp <= end


def _percent(numerator: int, denominator: int) -> float:
    if denominator == 0:
        return 0.0
    return 100.0 * numerator / denominator


def build_view(raw_dir: Path, features_dir: Path, predictions_dir: Path) -> dict[str, object]:
    features = read_dir(features_dir)
    raw_rows = read_dir(raw_dir)
    predictions = read_dir(predictions_dir)
    feature_times = [parse_timestamp(row.get("timestamp")) for row in features]
    feature_times = [stamp for stamp in feature_times if stamp is not None]
    end = max(feature_times) if feature_times else None
    start = end - WINDOW if end is not None else None

    window_features = []
    for row in features:
        stamp = parse_timestamp(row.get("timestamp"))
        if _in_window(stamp, start, end):
            window_features.append((stamp, row))

    orders_by_minute: dict[datetime, int] = {}
    for stamp, _row in window_features:
        minute = _minute(stamp)
        orders_by_minute[minute] = orders_by_minute.get(minute, 0) + 1
    hero_points = [
        {"Minute": minute.strftime("%H:%M"), "Orders": orders_by_minute[minute]}
        for minute in sorted(orders_by_minute)
    ]
    recent_cut = end - RECENT if end is not None else None
    recent = sum(1 for stamp, _row in window_features if recent_cut is not None and stamp > recent_cut)
    prior = len(window_features) - recent

    predictions_by_order = {}
    for row in predictions:
        order_id = str(row.get("order_id", "")).strip()
        if order_id:
            predictions_by_order[order_id] = row

    flags_by_minute: dict[datetime, list[int]] = {}
    joined_flags = []
    for stamp, row in window_features:
        prediction = predictions_by_order.get(str(row.get("order_id", "")).strip())
        if prediction is None:
            continue
        flag = 1 if str(prediction.get("predicted_late", "")).strip() == "1" else 0
        joined_flags.append(flag)
        minute = _minute(stamp)
        flags_by_minute.setdefault(minute, []).append(flag)
    flag_points = [
        {
            "Minute": minute.strftime("%H:%M"),
            "% flagged late": round(
                _percent(sum(flags_by_minute[minute]), len(flags_by_minute[minute])),
                1,
            ),
        }
        for minute in sorted(flags_by_minute)
    ]
    midpoint = len(flag_points) // 2
    earlier_points = flag_points[:midpoint] if midpoint else flag_points
    later_points = flag_points[midpoint:] if midpoint else flag_points
    earlier_rate = _mean(point["% flagged late"] for point in earlier_points)
    later_rate = _mean(point["% flagged late"] for point in later_points)

    considered = []
    for row in raw_rows:
        stamp = parse_timestamp(row.get("timestamp"))
        if end is None or stamp is None or _in_window(stamp, start, end):
            considered.append(row)
    failure_counts = {name: 0 for name in FIELD_LABELS}
    failed_rows = 0
    for row in considered:
        errors = field_errors(row)
        if errors:
            failed_rows += 1
        for name in errors:
            failure_counts[name] += 1
    bars = [
        {"label": FIELD_LABELS[name], "count": count}
        for name, count in sorted(failure_counts.items(), key=lambda item: (-item[1], item[0]))
        if count > 0
    ]
    if bars:
        failure_title = f"{bars[0]['label']} is the field that fails most"
    else:
        failure_title = "No bad fields in this window"

    checkpoint_id = ""
    if predictions_dir.exists():
        files = sorted(predictions_dir.glob("*.csv"), key=lambda path: path.stat().st_mtime)
        if files:
            newest_rows = read_prediction_checkpoint(files[-1])
            checkpoint_id = newest_rows

    late_rate = _percent(sum(joined_flags), len(joined_flags))
    drop_rate = _percent(failed_rows, len(considered))
    return {
        "kpis": [
            {"label": "Samples", "value": str(len(window_features))},
            {"label": "Drop rate", "value": f"{drop_rate:.0f}%"},
            {"label": "Late flag rate", "value": f"{late_rate:.0f}%" if joined_flags else "—"},
        ],
        "hero": {"title": volume_title(recent, prior), "points": hero_points},
        "flags": {"title": flag_title(earlier_rate, later_rate), "points": flag_points},
        "failures": {"title": failure_title, "bars": bars},
        "checkpoint_id": checkpoint_id,
    }


def _mean(values) -> float:
    items = list(values)
    if not items:
        return 0.0
    return sum(items) / len(items)


def read_prediction_checkpoint(path: Path) -> str:
    from pipeline.files import read_rows

    rows = read_rows(path)
    if not rows:
        return ""
    return str(rows[0].get("checkpoint_id", "")).strip()
