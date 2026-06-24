"""Historical data loading.

Reads OHLCV bars from CSV using only the stdlib so the backtester has no heavy
dependencies. Expected header (case-insensitive), comma-separated::

    timestamp,open,high,low,close,volume

``timestamp`` may be ISO-8601 (``2024-01-02T15:30:00``) or epoch seconds.
"""
from __future__ import annotations

import csv
from datetime import datetime, timezone
from typing import Iterable, List

from ..core.models import Bar

_ALIASES = {
    "time": "timestamp",
    "date": "timestamp",
    "datetime": "timestamp",
    "vol": "volume",
}


def _parse_time(raw: str) -> datetime:
    raw = raw.strip()
    # Epoch seconds?
    try:
        return datetime.fromtimestamp(float(raw), tz=timezone.utc)
    except ValueError:
        pass
    # ISO-8601, tolerating a trailing 'Z'.
    dt = datetime.fromisoformat(raw.replace("Z", "+00:00"))
    # Normalise to tz-aware UTC so mixed naive/epoch rows still sort together.
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt


def load_csv(path: str) -> List[Bar]:
    """Load bars from a CSV file, sorted ascending by timestamp."""
    with open(path, newline="") as fh:
        return list(parse_rows(fh))


def parse_rows(lines: Iterable[str]) -> List[Bar]:
    """Parse CSV ``lines`` into bars. Split out from :func:`load_csv` for tests."""
    reader = csv.DictReader(lines)
    if reader.fieldnames is None:
        return []
    norm = {f: _ALIASES.get(f.strip().lower(), f.strip().lower())
            for f in reader.fieldnames}

    bars: List[Bar] = []
    for row in reader:
        rec = {norm[k]: v for k, v in row.items() if k in norm}
        bars.append(Bar(
            timestamp=_parse_time(rec["timestamp"]),
            open=float(rec["open"]),
            high=float(rec["high"]),
            low=float(rec["low"]),
            close=float(rec["close"]),
            volume=float(rec.get("volume") or 0.0),
        ))
    bars.sort(key=lambda b: b.timestamp)
    return bars
