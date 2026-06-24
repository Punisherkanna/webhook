"""Bollinger Band breakout strategy.

Trades volatility expansion: go long when the close pushes above the upper band,
short when it closes below the lower band. The opposite band acts as a logical
invalidation level, but the protective stop is ATR-based and capped. Single
position only.
"""
from __future__ import annotations

from ..core.models import Signal, SignalType
from ..core.strategy import Strategy
from ..indicators.indicators import atr, bollinger


class BollingerBreakout(Strategy):
    """Params: ``period`` (20), ``num_std`` (2.0), ``atr_period`` (14),
    ``atr_stop`` (2.0), ``atr_target`` (3.0)."""

    def on_bar(self) -> Signal:
        period = int(self.params.get("period", 20))
        num_std = float(self.params.get("num_std", 2.0))

        closes = self.closes
        if len(closes) < period + 1:
            return Signal.none()

        upper, mid, lower = bollinger(closes, period, num_std)
        up, lo, md = upper[-1], lower[-1], mid[-1]
        up_prev, lo_prev = upper[-2], lower[-2]
        if None in (up, lo, md, up_prev, lo_prev):
            return Signal.none()

        price = closes[-1]
        prev = closes[-2]
        stop_dist = self._atr_distance(price)
        atr_stop = float(self.params.get("atr_stop", 2.0))
        atr_target = float(self.params.get("atr_target", 3.0))

        # Require the *close* to cross the band (prev inside, now outside) so we
        # act once per breakout rather than every bar spent outside the band.
        broke_up = prev <= up_prev and price > up
        broke_down = prev >= lo_prev and price < lo

        if broke_up:
            return Signal(
                SignalType.ENTER_LONG,
                stop_loss=price - stop_dist * atr_stop,
                take_profit=price + stop_dist * atr_target,
                reason="closed above upper band",
            )
        if broke_down:
            return Signal(
                SignalType.ENTER_SHORT,
                stop_loss=price + stop_dist * atr_stop,
                take_profit=price - stop_dist * atr_target,
                reason="closed below lower band",
            )
        return Signal.none()

    def _atr_distance(self, fallback_price: float) -> float:
        period = int(self.params.get("atr_period", 14))
        a = atr(self.highs, self.lows, self.closes, period)
        if a[-1]:
            return a[-1]
        return fallback_price * 0.001
