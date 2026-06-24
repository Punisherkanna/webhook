"""MACD trend strategy.

Enters in the direction of a MACD/signal-line crossover, but only when it agrees
with the longer-term trend (price above/below a slow EMA filter). The trend
filter keeps it from fading strong moves. Single position, ATR stop.
"""
from __future__ import annotations

from ..core.models import Signal, SignalType
from ..core.strategy import Strategy
from ..indicators.indicators import atr, ema, macd


class MACDTrend(Strategy):
    """Params: ``fast`` (12), ``slow`` (26), ``signal`` (9),
    ``trend_period`` (100), ``atr_period`` (14), ``atr_stop`` (2.0),
    ``atr_target`` (3.0)."""

    def on_bar(self) -> Signal:
        fast = int(self.params.get("fast", 12))
        slow = int(self.params.get("slow", 26))
        signal_p = int(self.params.get("signal", 9))
        trend_period = int(self.params.get("trend_period", 100))

        closes = self.closes
        if len(closes) < max(slow + signal_p, trend_period) + 2:
            return Signal.none()

        macd_line, signal_line, _ = macd(closes, fast, slow, signal_p)
        m_now, m_prev = macd_line[-1], macd_line[-2]
        s_now, s_prev = signal_line[-1], signal_line[-2]
        if None in (m_now, m_prev, s_now, s_prev):
            return Signal.none()

        trend = ema(closes, trend_period)[-1]
        if trend is None:
            return Signal.none()

        price = closes[-1]
        stop_dist = self._atr_distance(price)
        atr_stop = float(self.params.get("atr_stop", 2.0))
        atr_target = float(self.params.get("atr_target", 3.0))

        crossed_up = m_prev <= s_prev and m_now > s_now
        crossed_down = m_prev >= s_prev and m_now < s_now

        # Only take longs in an uptrend and shorts in a downtrend.
        if crossed_up and price > trend:
            return Signal(
                SignalType.ENTER_LONG,
                stop_loss=price - stop_dist * atr_stop,
                take_profit=price + stop_dist * atr_target,
                reason="MACD crossed up in uptrend",
            )
        if crossed_down and price < trend:
            return Signal(
                SignalType.ENTER_SHORT,
                stop_loss=price + stop_dist * atr_stop,
                take_profit=price - stop_dist * atr_target,
                reason="MACD crossed down in downtrend",
            )
        return Signal.none()

    def _atr_distance(self, fallback_price: float) -> float:
        period = int(self.params.get("atr_period", 14))
        a = atr(self.highs, self.lows, self.closes, period)
        if a[-1]:
            return a[-1]
        return fallback_price * 0.001
