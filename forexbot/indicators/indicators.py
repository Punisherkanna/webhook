"""Pure-Python technical indicators.

These operate on plain lists of floats so the core needs no numpy/pandas. Each
function returns a list aligned to the input length, with ``None`` for periods
that don't yet have enough data (the standard "warm-up" convention).
"""
from __future__ import annotations

import math
from typing import List, Optional


def sma(values: List[float], period: int) -> List[Optional[float]]:
    """Simple moving average."""
    if period <= 0:
        raise ValueError("period must be positive")
    out: List[Optional[float]] = [None] * len(values)
    running = 0.0
    for i, v in enumerate(values):
        running += v
        if i >= period:
            running -= values[i - period]
        if i >= period - 1:
            out[i] = running / period
    return out


def ema(values: List[float], period: int) -> List[Optional[float]]:
    """Exponential moving average, seeded with an SMA of the first ``period``."""
    if period <= 0:
        raise ValueError("period must be positive")
    out: List[Optional[float]] = [None] * len(values)
    if len(values) < period:
        return out
    k = 2.0 / (period + 1.0)
    seed = sum(values[:period]) / period
    out[period - 1] = seed
    prev = seed
    for i in range(period, len(values)):
        prev = values[i] * k + prev * (1.0 - k)
        out[i] = prev
    return out


def rsi(values: List[float], period: int = 14) -> List[Optional[float]]:
    """Wilder's Relative Strength Index."""
    if period <= 0:
        raise ValueError("period must be positive")
    out: List[Optional[float]] = [None] * len(values)
    if len(values) <= period:
        return out

    gains = 0.0
    losses = 0.0
    for i in range(1, period + 1):
        delta = values[i] - values[i - 1]
        gains += max(delta, 0.0)
        losses += max(-delta, 0.0)
    avg_gain = gains / period
    avg_loss = losses / period
    out[period] = _rsi_from(avg_gain, avg_loss)

    for i in range(period + 1, len(values)):
        delta = values[i] - values[i - 1]
        gain = max(delta, 0.0)
        loss = max(-delta, 0.0)
        avg_gain = (avg_gain * (period - 1) + gain) / period
        avg_loss = (avg_loss * (period - 1) + loss) / period
        out[i] = _rsi_from(avg_gain, avg_loss)
    return out


def _rsi_from(avg_gain: float, avg_loss: float) -> float:
    if avg_loss == 0.0:
        return 100.0
    rs = avg_gain / avg_loss
    return 100.0 - (100.0 / (1.0 + rs))


def atr(highs: List[float], lows: List[float], closes: List[float],
        period: int = 14) -> List[Optional[float]]:
    """Average True Range (Wilder smoothing)."""
    n = len(closes)
    if not (len(highs) == len(lows) == n):
        raise ValueError("highs, lows, closes must be equal length")
    out: List[Optional[float]] = [None] * n
    if n <= period:
        return out

    trs: List[float] = [highs[0] - lows[0]]
    for i in range(1, n):
        tr = max(
            highs[i] - lows[i],
            abs(highs[i] - closes[i - 1]),
            abs(lows[i] - closes[i - 1]),
        )
        trs.append(tr)

    first = sum(trs[1:period + 1]) / period
    out[period] = first
    prev = first
    for i in range(period + 1, n):
        prev = (prev * (period - 1) + trs[i]) / period
        out[i] = prev
    return out


def rolling_std(values: List[float], period: int) -> List[Optional[float]]:
    """Rolling population standard deviation over ``period`` samples."""
    if period <= 0:
        raise ValueError("period must be positive")
    out: List[Optional[float]] = [None] * len(values)
    for i in range(period - 1, len(values)):
        window = values[i - period + 1:i + 1]
        mean = sum(window) / period
        var = sum((x - mean) ** 2 for x in window) / period
        out[i] = math.sqrt(var)
    return out


def bollinger(values: List[float], period: int = 20, num_std: float = 2.0):
    """Bollinger Bands. Returns ``(upper, middle, lower)`` aligned lists.

    The middle band is the SMA; the outer bands are ``num_std`` rolling standard
    deviations away.
    """
    mid = sma(values, period)
    sd = rolling_std(values, period)
    upper: List[Optional[float]] = [None] * len(values)
    lower: List[Optional[float]] = [None] * len(values)
    for i in range(len(values)):
        if mid[i] is not None and sd[i] is not None:
            upper[i] = mid[i] + num_std * sd[i]
            lower[i] = mid[i] - num_std * sd[i]
    return upper, mid, lower


def macd(values: List[float], fast: int = 12, slow: int = 26,
         signal: int = 9):
    """MACD. Returns ``(macd_line, signal_line, histogram)`` aligned lists.

    ``macd_line = EMA(fast) - EMA(slow)``; ``signal_line = EMA(macd_line)``;
    ``histogram = macd_line - signal_line``. Entries are ``None`` until each
    component has warmed up.
    """
    if fast >= slow:
        raise ValueError("fast period must be < slow period")
    ema_fast = ema(values, fast)
    ema_slow = ema(values, slow)
    n = len(values)
    macd_line: List[Optional[float]] = [None] * n
    for i in range(n):
        if ema_fast[i] is not None and ema_slow[i] is not None:
            macd_line[i] = ema_fast[i] - ema_slow[i]

    # Signal EMA is computed only over the warmed-up portion of the MACD line.
    start = next((i for i, v in enumerate(macd_line) if v is not None), None)
    signal_line: List[Optional[float]] = [None] * n
    hist: List[Optional[float]] = [None] * n
    if start is not None:
        dense = [v for v in macd_line[start:]]
        sig_dense = ema(dense, signal)
        for offset, v in enumerate(sig_dense):
            idx = start + offset
            signal_line[idx] = v
            if v is not None and macd_line[idx] is not None:
                hist[idx] = macd_line[idx] - v
    return macd_line, signal_line, hist


def donchian(highs: List[float], lows: List[float], period: int = 20):
    """Donchian channel from the *prior* ``period`` bars (current bar excluded).

    Returns ``(upper, lower)`` where ``upper[i]`` is the highest high and
    ``lower[i]`` the lowest low over bars ``[i-period, i-1]``. Excluding the
    current bar makes a breakout test (``high > upper``) meaningful rather than
    trivially true.
    """
    if period <= 0:
        raise ValueError("period must be positive")
    n = len(highs)
    if len(lows) != n:
        raise ValueError("highs and lows must be equal length")
    upper: List[Optional[float]] = [None] * n
    lower: List[Optional[float]] = [None] * n
    for i in range(period, n):
        upper[i] = max(highs[i - period:i])
        lower[i] = min(lows[i - period:i])
    return upper, lower
