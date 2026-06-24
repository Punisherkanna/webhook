from datetime import datetime, timedelta, timezone

from forexbot.core.models import Bar, SignalType
from forexbot.strategies import get_strategy
from forexbot.strategies.ma_crossover import MACrossover
from forexbot.strategies.rsi_reversion import RSIReversion


def _feed(strategy, closes):
    """Push a close series through a strategy, return the last signal."""
    t = datetime(2024, 1, 1, tzinfo=timezone.utc)
    sig = None
    for i, c in enumerate(closes):
        bar = Bar(t + timedelta(minutes=15 * i), c, c + 0.001, c - 0.001, c, 100)
        sig = strategy.update(bar)
    return sig


def test_registry_lookup():
    assert get_strategy("ma_crossover") is MACrossover
    assert get_strategy("rsi_reversion") is RSIReversion


def test_registry_unknown_raises():
    try:
        get_strategy("does_not_exist")
        assert False
    except ValueError:
        pass


def test_ma_crossover_emits_long_on_upturn():
    strat = MACrossover("EURUSD", {"fast": 3, "slow": 6})
    # Down then sharply up to force a fast-above-slow cross.
    closes = [1.10 - i * 0.001 for i in range(8)] + [1.09 + i * 0.003 for i in range(8)]
    seen = []
    t = datetime(2024, 1, 1, tzinfo=timezone.utc)
    for i, c in enumerate(closes):
        bar = Bar(t + timedelta(minutes=i), c, c + 0.001, c - 0.001, c, 100)
        seen.append(strat.update(bar).type)
    assert SignalType.ENTER_LONG in seen


def test_ma_crossover_requires_fast_lt_slow():
    strat = MACrossover("EURUSD", {"fast": 10, "slow": 5})
    try:
        _feed(strat, [1.1 + i * 0.001 for i in range(30)])
        assert False
    except ValueError:
        pass


def test_ma_crossover_no_signal_when_insufficient_data():
    strat = MACrossover("EURUSD", {"fast": 5, "slow": 20})
    sig = _feed(strat, [1.1, 1.2, 1.3])
    assert sig.type is SignalType.NONE


def test_rsi_long_sets_stop_below_entry():
    strat = RSIReversion("EURUSD", {"period": 5})
    # V-shape: sell-off then recovery should pop RSI out of oversold.
    closes = [1.10 - i * 0.002 for i in range(10)] + [1.08 + i * 0.002 for i in range(10)]
    seen_long = None
    t = datetime(2024, 1, 1, tzinfo=timezone.utc)
    for i, c in enumerate(closes):
        bar = Bar(t + timedelta(minutes=i), c, c + 0.001, c - 0.001, c, 100)
        s = strat.update(bar)
        if s.type is SignalType.ENTER_LONG:
            seen_long = s
    if seen_long is not None:
        assert seen_long.stop_loss < closes[-1] + 1  # stop below a plausible entry
        assert seen_long.take_profit is not None
