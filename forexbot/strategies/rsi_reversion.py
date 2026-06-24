"""RSI mean-reversion strategy.

Enters long when RSI exits oversold (crosses up through ``oversold``) and short
when it exits overbought. This is a single-entry reversion model — it does NOT
add to losers, so it is not a martingale/grid scheme.
"""
from __future__ import annotations

from ..core.models import Signal, SignalType
from ..core.strategy import Strategy
from ..indicators.indicators import atr, rsi


class RSIReversion(Strategy):
    """Params: ``period`` (14), ``oversold`` (30), ``overbought`` (70),
    ``atr_period`` (14), ``atr_stop`` (2.0), ``atr_target`` (3.0)."""

    def on_bar(self) -> Signal:
        period = int(self.params.get("period", 14))
        oversold = float(self.params.get("oversold", 30))
        overbought = float(self.params.get("overbought", 70))

        closes = self.closes
        if len(closes) < period + 2:
            return Signal.none()

        r = rsi(closes, period)
        now, prev = r[-1], r[-2]
        if now is None or prev is None:
            return Signal.none()

        price = closes[-1]
        stop_dist = self._atr_distance(price)
        atr_stop = float(self.params.get("atr_stop", 2.0))
        atr_target = float(self.params.get("atr_target", 3.0))

        if prev <= oversold and now > oversold:
            return Signal(
                SignalType.ENTER_LONG,
                stop_loss=price - stop_dist * atr_stop,
                take_profit=price + stop_dist * atr_target,
                reason=f"RSI exited oversold ({now:.1f})",
            )
        if prev >= overbought and now < overbought:
            return Signal(
                SignalType.ENTER_SHORT,
                stop_loss=price + stop_dist * atr_stop,
                take_profit=price - stop_dist * atr_target,
                reason=f"RSI exited overbought ({now:.1f})",
            )
        return Signal.none()

    def _atr_distance(self, fallback_price: float) -> float:
        period = int(self.params.get("atr_period", 14))
        a = atr(self.highs, self.lows, self.closes, period)
        if a[-1]:
            return a[-1]
        return fallback_price * 0.001
