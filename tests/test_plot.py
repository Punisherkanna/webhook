from datetime import datetime, timedelta, timezone

from forexbot.backtest.engine import Backtester, BacktestConfig
from forexbot.backtest.plot import render_svg, save_equity_plot
from forexbot.core.models import Bar, Signal, SignalType
from forexbot.core.strategy import Strategy


class EnterOnceLong(Strategy):
    def on_bar(self):
        if len(self.bars) == 1:
            p = self.bars[-1].close
            return Signal(SignalType.ENTER_LONG, stop_loss=p - 0.002,
                          take_profit=p + 0.002)
        return Signal.none()


def _result():
    t = datetime(2024, 1, 1, tzinfo=timezone.utc)
    closes = [1.1000 + i * 0.0005 for i in range(20)]
    bars = [Bar(t + timedelta(minutes=15 * i), c, c + 0.0005, c - 0.0005, c, 100)
            for i, c in enumerate(closes)]
    cfg = BacktestConfig(symbol="EURUSD", spread_pips=0.0, commission_per_lot=0.0)
    return Backtester(EnterOnceLong("EURUSD"), cfg).run(bars)


def test_render_svg_is_wellformed():
    svg = render_svg(_result())
    assert svg.lstrip().startswith("<?xml")
    assert "<svg" in svg and "</svg>" in svg
    assert "polyline" in svg          # the equity line
    assert "EURUSD" in svg            # title carries the symbol


def test_save_svg_writes_file(tmp_path):
    out = save_equity_plot(_result(), str(tmp_path / "eq.svg"))
    assert out.endswith(".svg")
    content = (tmp_path / "eq.svg").read_text()
    assert content.count("<svg") == 1


def test_unsupported_extension_raises(tmp_path):
    try:
        save_equity_plot(_result(), str(tmp_path / "eq.pdf"))
        assert False
    except ValueError:
        pass


def test_flat_curve_does_not_crash():
    # A degenerate equity curve (no trades) must still render.
    class Flat(Strategy):
        def on_bar(self):
            return Signal.none()

    t = datetime(2024, 1, 1, tzinfo=timezone.utc)
    bars = [Bar(t + timedelta(minutes=i), 1.1, 1.1, 1.1, 1.1, 1) for i in range(5)]
    res = Backtester(Flat("EURUSD"), BacktestConfig()).run(bars)
    svg = render_svg(res)
    assert "<svg" in svg
