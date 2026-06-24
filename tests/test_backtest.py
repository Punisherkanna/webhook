from datetime import datetime, timedelta, timezone

from forexbot.backtest.data import parse_rows
from forexbot.backtest.engine import Backtester, BacktestConfig
from forexbot.core.models import Bar, Side, Signal, SignalType
from forexbot.core.risk import RiskConfig
from forexbot.core.strategy import Strategy


def _bars(closes, highs=None, lows=None):
    t = datetime(2024, 1, 1, tzinfo=timezone.utc)
    out = []
    for i, c in enumerate(closes):
        hi = highs[i] if highs else c + 0.0005
        lo = lows[i] if lows else c - 0.0005
        out.append(Bar(t + timedelta(minutes=15 * i), c, hi, lo, c, 100))
    return out


class EnterOnceLong(Strategy):
    """Emits a single long entry on bar index 0, then nothing."""

    def on_bar(self):
        if len(self.bars) == 1:
            price = self.bars[-1].close
            return Signal(SignalType.ENTER_LONG,
                          stop_loss=price - 0.0020,
                          take_profit=price + 0.0020)
        return Signal.none()


def test_csv_parsing_roundtrip():
    lines = [
        "timestamp,open,high,low,close,volume",
        "2024-01-02T00:00:00,1.1,1.2,1.0,1.15,100",
        "1704153600,1.15,1.18,1.10,1.12,50",  # epoch seconds
    ]
    bars = parse_rows(lines)
    assert len(bars) == 2
    assert bars[0].close == 1.15
    assert bars[1].open == 1.15


def test_backtest_take_profit_hit_is_profitable():
    # Price drifts up so the long's take-profit triggers.
    closes = [1.1000 + i * 0.0005 for i in range(20)]
    bars = _bars(closes)
    strat = EnterOnceLong("EURUSD")
    cfg = BacktestConfig(symbol="EURUSD", starting_equity=10_000,
                         spread_pips=0.0, commission_per_lot=0.0,
                         risk=RiskConfig(risk_per_trade=0.01))
    result = Backtester(strat, cfg).run(bars)
    assert result.num_trades == 1
    assert result.trades[0].side is Side.BUY
    assert result.trades[0].pnl > 0
    assert result.ending_equity > result.starting_equity


def test_backtest_stop_loss_hit_is_a_loss():
    # Price drifts down so the long's stop triggers.
    closes = [1.1000 - i * 0.0005 for i in range(20)]
    bars = _bars(closes)
    strat = EnterOnceLong("EURUSD")
    cfg = BacktestConfig(symbol="EURUSD", starting_equity=10_000,
                         spread_pips=0.0, commission_per_lot=0.0)
    result = Backtester(strat, cfg).run(bars)
    assert result.num_trades == 1
    assert result.trades[0].pnl < 0
    assert result.trades[0].reason == "stop loss"


def test_metrics_are_sane():
    closes = [1.1000 + i * 0.0005 for i in range(20)]
    result = Backtester(EnterOnceLong("EURUSD"),
                        BacktestConfig(spread_pips=0.0, commission_per_lot=0.0)
                        ).run(_bars(closes))
    assert 0 <= result.win_rate <= 100
    assert result.max_drawdown_pct >= 0
    assert len(result.equity_curve) == len(closes) + 1


def test_no_signal_no_trades():
    class Flat(Strategy):
        def on_bar(self):
            return Signal.none()

    result = Backtester(Flat("EURUSD"), BacktestConfig()).run(_bars([1.1] * 10))
    assert result.num_trades == 0
    assert result.ending_equity == result.starting_equity
