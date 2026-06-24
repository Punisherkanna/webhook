"""Moving-average crossover strategy.

Goes long when the fast MA crosses above the slow MA, short on the reverse.
Stops/targets are derived from ATR so they adapt to volatility.
"""
from __future__ import annotations

from ..core.models import Signal, SignalType
from ..core.strategy import Strategy
from ..indicators.indicators import atr, sma


class MACrossover(Strategy):
    """Params: ``fast`` (default 10), ``slow`` (30), ``atr_period`` (14),
    ``atr_stop`` (2.0), ``atr_target`` (3.0)."""

    def on_bar(self) -> Signal:
        fast = int(self.params.get("fast", 10))
        slow = int(self.params.get("slow", 30))
        if fast >= slow:
            raise ValueError("fast period must be < slow period")

        closes = self.closes
        if len(closes) < slow + 1:
            return Signal.none()

        fast_ma = sma(closes, fast)
        slow_ma = sma(closes, slow)

        f_now, f_prev = fast_ma[-1], fast_ma[-2]
        s_now, s_prev = slow_ma[-1], slow_ma[-2]
        if None in (f_now, f_prev, s_now, s_prev):
            return Signal.none()

        crossed_up = f_prev <= s_prev and f_now > s_now
        crossed_down = f_prev >= s_prev and f_now < s_now
        if not (crossed_up or crossed_down):
            return Signal.none()

        price = closes[-1]
        stop_dist = self._atr_distance(price)

        if crossed_up:
            return Signal(
                SignalType.ENTER_LONG,
                stop_loss=price - stop_dist * self._mult("atr_stop", 2.0),
                take_profit=price + stop_dist * self._mult("atr_target", 3.0),
                reason="fast crossed above slow",
            )
        return Signal(
            SignalType.ENTER_SHORT,
            stop_loss=price + stop_dist * self._mult("atr_stop", 2.0),
            take_profit=price - stop_dist * self._mult("atr_target", 3.0),
            reason="fast crossed below slow",
        )

    def _atr_distance(self, fallback_price: float) -> float:
        period = int(self.params.get("atr_period", 14))
        a = atr(self.highs, self.lows, self.closes, period)
        if a[-1]:
            return a[-1]
        # Fallback before ATR warms up: 0.1% of price.
        return fallback_price * 0.001

    def _mult(self, key: str, default: float) -> float:
        return float(self.params.get(key, default))
