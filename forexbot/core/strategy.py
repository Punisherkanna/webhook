"""Strategy base class.

A strategy is broker-agnostic: it consumes bars and emits :class:`Signal`s. The
same strategy object runs unchanged in the backtester and against live MT5 /
NinjaTrader feeds.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import List

from .models import Bar, Signal


class Strategy(ABC):
    """Subclass this and implement :meth:`on_bar`.

    The engine pushes one bar at a time via :meth:`update`, which appends to the
    rolling ``self.bars`` history and then calls :meth:`on_bar`. Strategies read
    history from ``self.bars`` (most recent last).
    """

    def __init__(self, symbol: str, params: dict | None = None) -> None:
        self.symbol = symbol
        self.params = params or {}
        self.bars: List[Bar] = []

    @property
    def closes(self) -> List[float]:
        return [b.close for b in self.bars]

    @property
    def highs(self) -> List[float]:
        return [b.high for b in self.bars]

    @property
    def lows(self) -> List[float]:
        return [b.low for b in self.bars]

    def update(self, bar: Bar) -> Signal:
        self.bars.append(bar)
        return self.on_bar()

    @abstractmethod
    def on_bar(self) -> Signal:
        """Return a :class:`Signal` based on ``self.bars``."""
        raise NotImplementedError

    @property
    def name(self) -> str:
        return type(self).__name__
