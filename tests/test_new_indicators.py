import math

from forexbot.indicators import bollinger, donchian, macd, rolling_std, sma


def test_rolling_std_constant_is_zero():
    out = rolling_std([3.0] * 6, 3)
    assert out[:2] == [None, None]
    assert all(abs(v) < 1e-12 for v in out[2:])


def test_rolling_std_known_value():
    # population std of [1,2,3] = sqrt(2/3)
    out = rolling_std([1, 2, 3], 3)
    assert out[2] == math.sqrt(2.0 / 3.0)


def test_bollinger_middle_is_sma_and_bands_straddle():
    vals = [1, 2, 3, 4, 5, 6, 7, 8]
    upper, mid, lower = bollinger(vals, 4, 2.0)
    assert mid[3] == sma(vals, 4)[3]
    for i in range(3, len(vals)):
        assert lower[i] < mid[i] < upper[i]


def test_macd_zero_when_flat():
    macd_line, signal_line, hist = macd([5.0] * 60, 12, 26, 9)
    # On a flat series both EMAs equal the price, so MACD ~ 0.
    assert abs(macd_line[-1]) < 1e-9
    assert abs(hist[-1]) < 1e-9


def test_macd_validates_periods():
    try:
        macd([1.0] * 10, 26, 12, 9)
        assert False
    except ValueError:
        pass


def test_donchian_excludes_current_bar():
    highs = [1, 2, 3, 4, 10]
    lows = [1, 1, 1, 1, 0]
    upper, lower = donchian(highs, lows, 4)
    # At index 4, channel is over bars 0..3 (excludes the spike at index 4).
    assert upper[4] == 4
    assert lower[4] == 1
    assert upper[3] is None  # not enough prior bars yet


def test_donchian_validates_lengths():
    try:
        donchian([1, 2, 3], [1, 2], 2)
        assert False
    except ValueError:
        pass
