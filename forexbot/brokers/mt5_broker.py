"""MetaTrader 5 broker adapter.

Wraps the official ``MetaTrader5`` Python package (Windows-only, talks to a
running MT5 terminal). The import is lazy so the rest of the project — core,
backtester, tests — works on any platform without MT5 installed.

Install on a Windows host with::

    pip install MetaTrader5

Timeframe strings ("M1", "M5", "H1", "D1", ...) are mapped to MT5 constants.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import List, Optional

from ..core.broker import Broker
from ..core.models import Account, Bar, Order, OrderType, Position, Side

_TIMEFRAMES = {
    "M1": "TIMEFRAME_M1", "M5": "TIMEFRAME_M5", "M15": "TIMEFRAME_M15",
    "M30": "TIMEFRAME_M30", "H1": "TIMEFRAME_H1", "H4": "TIMEFRAME_H4",
    "D1": "TIMEFRAME_D1", "W1": "TIMEFRAME_W1",
}


def _load_mt5():
    try:
        import MetaTrader5 as mt5  # type: ignore
    except ImportError as exc:  # pragma: no cover - depends on host
        raise RuntimeError(
            "MetaTrader5 package not installed. Run `pip install MetaTrader5` "
            "on a Windows host with the MT5 terminal."
        ) from exc
    return mt5


class MT5Broker(Broker):
    def __init__(self, login: Optional[int] = None, password: str = "",
                 server: str = "", path: Optional[str] = None,
                 magic: int = 234000) -> None:
        self.login = login
        self.password = password
        self.server = server
        self.path = path
        self.magic = magic
        self._mt5 = None

    # --- lifecycle ----------------------------------------------------------
    def connect(self) -> None:
        mt5 = _load_mt5()
        kwargs = {}
        if self.path:
            kwargs["path"] = self.path
        if self.login:
            kwargs.update(login=self.login, password=self.password,
                          server=self.server)
        if not mt5.initialize(**kwargs):
            raise RuntimeError(f"MT5 initialize failed: {mt5.last_error()}")
        self._mt5 = mt5

    def disconnect(self) -> None:
        if self._mt5 is not None:
            self._mt5.shutdown()
            self._mt5 = None

    def _require(self):
        if self._mt5 is None:
            raise RuntimeError("MT5Broker not connected; call connect() first")
        return self._mt5

    # --- Broker interface ---------------------------------------------------
    def get_account(self) -> Account:
        mt5 = self._require()
        info = mt5.account_info()
        if info is None:
            raise RuntimeError(f"account_info failed: {mt5.last_error()}")
        return Account(balance=info.balance, equity=info.equity,
                       currency=info.currency, margin=info.margin)

    def get_bars(self, symbol: str, timeframe: str, count: int) -> List[Bar]:
        mt5 = self._require()
        tf_name = _TIMEFRAMES.get(timeframe.upper())
        if tf_name is None:
            raise ValueError(f"unsupported timeframe: {timeframe}")
        tf = getattr(mt5, tf_name)
        rates = mt5.copy_rates_from_pos(symbol, tf, 0, count)
        if rates is None:
            raise RuntimeError(f"copy_rates failed: {mt5.last_error()}")
        return [
            Bar(
                timestamp=datetime.fromtimestamp(r["time"], tz=timezone.utc),
                open=float(r["open"]), high=float(r["high"]),
                low=float(r["low"]), close=float(r["close"]),
                volume=float(r["tick_volume"]),
            )
            for r in rates
        ]

    def get_positions(self, symbol: Optional[str] = None) -> List[Position]:
        mt5 = self._require()
        raw = mt5.positions_get(symbol=symbol) if symbol else mt5.positions_get()
        if raw is None:
            return []
        out = []
        for p in raw:
            out.append(Position(
                symbol=p.symbol,
                side=Side.BUY if p.type == mt5.POSITION_TYPE_BUY else Side.SELL,
                volume=p.volume,
                entry_price=p.price_open,
                open_time=datetime.fromtimestamp(p.time, tz=timezone.utc),
                stop_loss=p.sl or None,
                take_profit=p.tp or None,
                id=str(p.ticket),
            ))
        return out

    def place_order(self, order: Order) -> Order:
        mt5 = self._require()
        tick = mt5.symbol_info_tick(order.symbol)
        if tick is None:
            raise RuntimeError(f"no tick for {order.symbol}")
        is_buy = order.side is Side.BUY
        price = order.price or (tick.ask if is_buy else tick.bid)
        request = {
            "action": mt5.TRADE_ACTION_DEAL,
            "symbol": order.symbol,
            "volume": float(order.volume),
            "type": mt5.ORDER_TYPE_BUY if is_buy else mt5.ORDER_TYPE_SELL,
            "price": price,
            "deviation": 20,
            "magic": self.magic,
            "comment": order.comment or "forexbot",
            "type_time": mt5.ORDER_TIME_GTC,
            "type_filling": mt5.ORDER_FILLING_IOC,
        }
        if order.stop_loss is not None:
            request["sl"] = order.stop_loss
        if order.take_profit is not None:
            request["tp"] = order.take_profit

        result = mt5.order_send(request)
        if result is None or result.retcode != mt5.TRADE_RETCODE_DONE:
            raise RuntimeError(f"order_send failed: {getattr(result, 'comment', mt5.last_error())}")
        order.id = str(result.order)
        return order

    def close_position(self, position: Position) -> None:
        mt5 = self._require()
        tick = mt5.symbol_info_tick(position.symbol)
        is_buy = position.side is Side.BUY
        price = tick.bid if is_buy else tick.ask
        request = {
            "action": mt5.TRADE_ACTION_DEAL,
            "symbol": position.symbol,
            "volume": float(position.volume),
            # Closing a buy means selling, and vice-versa.
            "type": mt5.ORDER_TYPE_SELL if is_buy else mt5.ORDER_TYPE_BUY,
            "position": int(position.id),
            "price": price,
            "deviation": 20,
            "magic": self.magic,
            "comment": "forexbot close",
            "type_time": mt5.ORDER_TIME_GTC,
            "type_filling": mt5.ORDER_FILLING_IOC,
        }
        result = mt5.order_send(request)
        if result is None or result.retcode != mt5.TRADE_RETCODE_DONE:
            raise RuntimeError(f"close failed: {getattr(result, 'comment', mt5.last_error())}")
