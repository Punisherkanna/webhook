import math

from forexbot.indicators import atr, ema, rsi, sma


def test_sma_basic():
    out = sma([1, 2, 3, 4, 5], 3)
    assert out[:2] == [None, None]
    assert out[2] == 2.0  # (1+2+3)/3
    assert out[3] == 3.0
    assert out[4] == 4.0


def test_sma_constant_series():
    out = sma([5.0] * 10, 4)
    assert all(v == 5.0 for v in out[3:])


def test_ema_seed_is_sma():
    values = [1, 2, 3, 4, 5, 6]
    out = ema(values, 3)
    assert out[2] == sma(values, 3)[2]  # seeded with SMA
    assert out[-1] is not None


def test_rsi_all_gains_is_100():
    out = rsi(list(range(1, 30)), 14)
    assert out[-1] == 100.0


def test_rsi_bounds():
    vals = [math.sin(i / 5.0) + i * 0.01 for i in range(100)]
    out = rsi(vals, 14)
    for v in out:
        if v is not None:
            assert 0.0 <= v <= 100.0


def test_atr_positive():
    highs = [i + 1.5 for i in range(50)]
    lows = [i for i in range(50)]
    closes = [i + 0.5 for i in range(50)]
    out = atr(highs, lows, closes, 14)
    assert out[13] is None
    assert out[14] is not None
    assert all(v > 0 for v in out[14:])


def test_period_validation():
    for fn in (sma, ema, rsi):
        try:
            fn([1, 2, 3], 0)
            assert False, "expected ValueError"
        except ValueError:
            pass
