"""Tiny CSV bar reader shared by file-bridge brokers."""
from __future__ import annotations

from pathlib import Path
from typing import List, Union

from ..backtest.data import load_csv
from ..core.models import Bar


def read_bar_csv(path: Union[str, Path]) -> List[Bar]:
    p = Path(path)
    if not p.exists():
        raise FileNotFoundError(f"bar CSV not found: {p}")
    return load_csv(str(p))
