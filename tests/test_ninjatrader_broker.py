"""Tests for the NinjaTrader file-bridge adapter — no NinjaTrader required."""
from forexbot.brokers.ninjatrader_broker import NinjaTraderBroker
from forexbot.core.models import Order, Position, Side


def test_place_order_writes_oif_command(tmp_path):
    inc = tmp_path / "incoming"
    nt = NinjaTraderBroker(account="Sim101", incoming_dir=str(inc))
    nt.connect()
    order = Order(symbol="EURUSD", side=Side.BUY, volume=1.0)
    nt.place_order(order)

    files = list(inc.glob("oif_*.txt"))
    assert len(files) == 1
    content = files[0].read_text().strip()
    assert content.startswith("PLACE;Sim101;EURUSD;BUY;1;MARKET")
    assert order.id is not None


def test_place_order_with_sl_tp_writes_oco(tmp_path):
    inc = tmp_path / "incoming"
    nt = NinjaTraderBroker(account="Sim101", incoming_dir=str(inc))
    nt.connect()
    order = Order(symbol="EURUSD", side=Side.BUY, volume=2.0,
                  stop_loss=1.0950, take_profit=1.1050)
    nt.place_order(order)
    contents = sorted(f.read_text() for f in inc.glob("oif_*.txt"))
    joined = "\n".join(contents)
    assert "PLACE;Sim101;EURUSD;BUY;2;MARKET" in joined
    assert "SELL;2;STOP;;1.09500" in joined   # protective stop
    assert "SELL;2;LIMIT;1.10500" in joined    # protective target


def test_close_position_writes_command(tmp_path):
    inc = tmp_path / "incoming"
    nt = NinjaTraderBroker(account="Sim101", incoming_dir=str(inc))
    nt.connect()
    pos = Position(symbol="EURUSD", side=Side.BUY, volume=1.0,
                   entry_price=1.1, open_time=None, id="1")
    nt.close_position(pos)
    files = list(inc.glob("oif_*.txt"))
    assert files[0].read_text().strip() == "CLOSEPOSITION;Sim101;EURUSD"


def test_get_positions_reads_state_file(tmp_path):
    inc = tmp_path / "incoming"
    state = tmp_path / "state"
    state.mkdir()
    (state / "positions.csv").write_text(
        "symbol,side,qty,avg_price\nEURUSD,BUY,1.5,1.1000\n"
    )
    nt = NinjaTraderBroker(incoming_dir=str(inc), state_dir=str(state))
    nt.connect()
    positions = nt.get_positions("EURUSD")
    assert len(positions) == 1
    assert positions[0].side is Side.BUY
    assert positions[0].volume == 1.5


def test_get_positions_missing_file_is_empty(tmp_path):
    nt = NinjaTraderBroker(incoming_dir=str(tmp_path / "incoming"),
                           state_dir=str(tmp_path / "state"))
    nt.connect()
    assert nt.get_positions() == []


def test_get_bars_without_data_dir_raises(tmp_path):
    nt = NinjaTraderBroker(incoming_dir=str(tmp_path / "incoming"))
    nt.connect()
    try:
        nt.get_bars("EURUSD", "M15", 10)
        assert False
    except RuntimeError as e:
        assert "does not stream bars" in str(e)
