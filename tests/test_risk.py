import pytest

from forexbot.core.risk import RiskConfig, RiskManager, pip_size


def test_pip_size():
    assert pip_size("EURUSD") == 0.0001
    assert pip_size("USDJPY") == 0.01
    assert pip_size("eurjpy") == 0.01


def test_size_for_stop_risks_expected_cash():
    rm = RiskManager(RiskConfig(risk_per_trade=0.01, lot_step=0.01, min_lots=0.01))
    # 20-pip stop on EURUSD, $10k equity, 1% risk => risk $100.
    # pip value per lot = 0.0001 * 100000 = $10/pip. 20 pips => $200/lot.
    # lots = 100 / 200 = 0.5
    lots = rm.size_for_stop(10_000, "EURUSD", 1.1000, 1.0980)
    assert lots == pytest.approx(0.5, abs=1e-9)


def test_zero_stop_distance_returns_zero():
    rm = RiskManager(RiskConfig())
    assert rm.size_for_stop(10_000, "EURUSD", 1.1, 1.1) == 0.0


def test_below_min_lots_returns_zero():
    rm = RiskManager(RiskConfig(risk_per_trade=0.01, min_lots=0.1))
    # Tiny equity makes raw lots < min_lots.
    lots = rm.size_for_stop(100, "EURUSD", 1.1000, 1.0900)
    assert lots == 0.0


def test_clamped_to_max_lots():
    rm = RiskManager(RiskConfig(risk_per_trade=1.0, max_lots=2.0, min_lots=0.01))
    lots = rm.size_for_stop(1_000_000, "EURUSD", 1.1000, 1.0999)
    assert lots == 2.0


def test_lot_step_rounding():
    rm = RiskManager(RiskConfig(lot_step=0.1, min_lots=0.1))
    lots = rm.round_lots(0.34)
    assert lots == pytest.approx(0.3)


def test_invalid_risk_rejected():
    with pytest.raises(ValueError):
        RiskConfig(risk_per_trade=0)
    with pytest.raises(ValueError):
        RiskConfig(risk_per_trade=1.5)
