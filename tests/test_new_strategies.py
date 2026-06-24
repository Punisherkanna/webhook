from datetime import datetime, timedelta, timezone

from forexbot.core.models import Bar, SignalType
from forexbot.strategies import get_strategy
from forexbot.strategies.bollinger_breakout import BollingerBreakout
from forexbot.strategies.donchian_breakout import DonchianBreakout
from forexbot.strategies.macd_trend import MACDTrend


def _run(strategy, closes, highs=None, lows=None):
    """Feed a series and collect every signal type emitted."""
    t = datetime(2024, 1, 1, tzinfo=timezone.utc)
    seen = []
    for i, c in enumerate(closes):
        hi = highs[i] if highs else c + 0.0005
        lo = lows[i] if lows else c - 0.0005
        bar = Bar(t + timedelta(minutes=i), c, hi, lo, c, 100)
        seen.append(strategy.update(bar))
    return seen


def test_new_strategies_registered():
    assert get_strategy("donchian_breakout") is DonchianBreakout
    assert get_strategy("macd_trend") is MACDTrend
    assert get_strategy("bollinger_breakout") is BollingerBreakout


def test_donchian_long_on_new_high():
    strat = DonchianBreakout("EURUSD", {"period": 10})
    # Flat range, then a decisive break above the prior high.
    closes = [1.10 + (i % 3) * 0.0005 for i in range(20)] + [1.12, 1.13]
    signals = _run(strat, closes)
    assert any(s.type is SignalType.ENTER_LONG for s in signals)


def test_donchian_short_on_new_low():
    strat = DonchianBreakout("EURUSD", {"period": 10})
    closes = [1.10 + (i % 3) * 0.0005 for i in range(20)] + [1.08, 1.07]
    signals = _run(strat, closes)
    assert any(s.type is SignalType.ENTER_SHORT for s in signals)


def test_donchian_warmup_no_signal():
    strat = DonchianBreakout("EURUSD", {"period": 20})
    signals = _run(strat, [1.1, 1.2, 1.3])
    assert all(s.type is SignalType.NONE for s in signals)


def test_macd_trend_long_in_uptrend():
    strat = MACDTrend("EURUSD", {"fast": 5, "slow": 12, "signal": 4,
                                 "trend_period": 20})
    # Steady uptrend so the trend filter allows longs and MACD crosses up.
    closes = [1.10 + i * 0.0008 for i in range(160)]
    signals = _run(strat, closes)
    assert any(s.type is SignalType.ENTER_LONG for s in signals)
    # Trend filter must block shorts in a clean uptrend.
    assert all(s.type is not SignalType.ENTER_SHORT for s in signals)


def test_macd_validates_fast_lt_slow():
    strat = MACDTrend("EURUSD", {"fast": 20, "slow": 10})
    try:
        _run(strat, [1.1 + i * 0.001 for i in range(200)])
        assert False
    except ValueError:
        pass


def test_bollinger_long_on_upper_break():
    strat = BollingerBreakout("EURUSD", {"period": 10, "num_std": 2.0})
    # Quiet, then a close that pops above the upper band.
    closes = [1.10 + (i % 2) * 0.0002 for i in range(20)] + [1.105]
    signals = _run(strat, closes)
    assert any(s.type is SignalType.ENTER_LONG for s in signals)


def test_bollinger_long_sets_protective_levels():
    strat = BollingerBreakout("EURUSD", {"period": 10})
    closes = [1.10 + (i % 2) * 0.0002 for i in range(20)] + [1.105]
    longs = [s for s in _run(strat, closes) if s.type is SignalType.ENTER_LONG]
    assert longs
    s = longs[0]
    assert s.stop_loss is not None and s.take_profit is not None
    assert s.stop_loss < s.take_profit
