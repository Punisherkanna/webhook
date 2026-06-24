"""Donchian channel breakout strategy.

A classic trend-following model (the core of the "Turtle" system): go long when
price breaks above the highest high of the prior N bars, short when it breaks
below the lowest low. Single position, ATR-based protective stop — not a grid or
martingale.
"""
from __future__ import annotations

from ..core.models import Signal, SignalType
from ..core.strategy import Strategy
from ..indicators.indicators import atr, donchian


class DonchianBreakout(Strategy):
    """Params: ``period`` (20), ``atr_period`` (14), ``atr_stop`` (2.0),
    ``atr_target`` (4.0)."""

    def on_bar(self) -> Signal:
        period = int(self.params.get("period", 20))
        if len(self.bars) < period + 1:
            return Signal.none()

        upper, lower = donchian(self.highs, self.lows, period)
        up, lo = upper[-1], lower[-1]
        if up is None or lo is None:
            return Signal.none()

        bar = self.bars[-1]
        price = bar.close
        stop_dist = self._atr_distance(price)
        atr_stop = float(self.params.get("atr_stop", 2.0))
        atr_target = float(self.params.get("atr_target", 4.0))

        # Breakout confirmed on the bar's high/low piercing the prior channel.
        if bar.high > up:
            return Signal(
                SignalType.ENTER_LONG,
                stop_loss=price - stop_dist * atr_stop,
                take_profit=price + stop_dist * atr_target,
                reason=f"broke {period}-bar high {up:.5f}",
            )
        if bar.low < lo:
            return Signal(
                SignalType.ENTER_SHORT,
                stop_loss=price + stop_dist * atr_stop,
                take_profit=price - stop_dist * atr_target,
                reason=f"broke {period}-bar low {lo:.5f}",
            )
        return Signal.none()

    def _atr_distance(self, fallback_price: float) -> float:
        period = int(self.params.get("atr_period", 14))
        a = atr(self.highs, self.lows, self.closes, period)
        if a[-1]:
            return a[-1]
        return fallback_price * 0.001
