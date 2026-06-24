from datetime import datetime, timedelta, timezone

from forexbot.brokers.paper import PaperBroker
from forexbot.core.engine import EngineConfig, TradingEngine
from forexbot.core.models import Bar, Order, Side, SignalType
from forexbot.core.risk import RiskConfig
from forexbot.core.strategy import Strategy
from forexbot.core.models import Signal


def _bar(i, price):
    t = datetime(2024, 1, 1, tzinfo=timezone.utc) + timedelta(minutes=15 * i)
    return Bar(t, price, price + 0.001, price - 0.001, price, 100)


def test_paper_broker_open_close_pnl():
    b = PaperBroker(starting_balance=10_000)
    b.connect()
    b.push_bar("EURUSD", _bar(0, 1.1000))
    order = Order(symbol="EURUSD", side=Side.BUY, volume=1.0)
    b.place_order(order)
    assert order.id is not None
    assert len(b.get_positions("EURUSD")) == 1

    b.push_bar("EURUSD", _bar(1, 1.1010))  # +10 pips
    pos = b.get_positions("EURUSD")[0]
    b.close_position(pos)
    assert b.get_positions("EURUSD") == []
    # +0.0010 * 1 lot * 100k = +$100
    assert round(b.balance - 10_000, 2) == 100.0


class AlwaysLong(Strategy):
    """Signals a long on every bar. The engine acts only on the latest bar, and
    won't re-enter once a position is open, so this is safe to leave 'always on'."""

    def on_bar(self):
        p = self.bars[-1].close
        return Signal(SignalType.ENTER_LONG, stop_loss=p - 0.002,
                      take_profit=p + 0.002)


def test_engine_dry_run_does_not_place():
    b = PaperBroker()
    b.connect()
    for i in range(3):
        b.push_bar("EURUSD", _bar(i, 1.10 + i * 0.001))
    eng = TradingEngine(b, AlwaysLong("EURUSD"), RiskConfig(),
                        EngineConfig(symbol="EURUSD", dry_run=True))
    order = eng.poll_once()
    assert order is not None             # an intended order is returned
    assert b.get_positions("EURUSD") == []  # but nothing was actually placed


def test_engine_live_places_order():
    b = PaperBroker()
    b.connect()
    for i in range(3):
        b.push_bar("EURUSD", _bar(i, 1.10 + i * 0.001))
    eng = TradingEngine(b, AlwaysLong("EURUSD"), RiskConfig(),
                        EngineConfig(symbol="EURUSD", dry_run=False))
    eng.poll_once()
    assert len(b.get_positions("EURUSD")) == 1
