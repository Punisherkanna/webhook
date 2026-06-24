"""In-memory paper-trading broker.

Useful for dry-running the live engine without any external dependency or real
money. Feed it bars via :meth:`push_bar`; it fills market orders at the latest
close and tracks positions/equity locally.
"""
from __future__ import annotations

import itertools
from datetime import datetime, timezone
from typing import Dict, List, Optional

from ..core.broker import Broker
from ..core.models import Account, Bar, Order, Position, Side


class PaperBroker(Broker):
    def __init__(self, starting_balance: float = 10_000.0,
                 contract_size: float = 100_000.0) -> None:
        self.balance = starting_balance
        self.contract_size = contract_size
        self._bars: Dict[str, List[Bar]] = {}
        self._positions: List[Position] = []
        self._ids = itertools.count(1)
        self._connected = False

    # --- lifecycle ----------------------------------------------------------
    def connect(self) -> None:
        self._connected = True

    def disconnect(self) -> None:
        self._connected = False

    # --- data feed ----------------------------------------------------------
    def push_bar(self, symbol: str, bar: Bar) -> None:
        """Append a bar to the simulated history for ``symbol``."""
        self._bars.setdefault(symbol, []).append(bar)

    def _last_price(self, symbol: str) -> float:
        bars = self._bars.get(symbol)
        if not bars:
            raise RuntimeError(f"no price data for {symbol}")
        return bars[-1].close

    # --- Broker interface ---------------------------------------------------
    def get_account(self) -> Account:
        equity = self.balance + sum(
            p.unrealized_pnl(self._last_price(p.symbol), self.contract_size)
            for p in self._positions
        )
        return Account(balance=self.balance, equity=equity,
                       positions=list(self._positions))

    def get_bars(self, symbol: str, timeframe: str, count: int) -> List[Bar]:
        return self._bars.get(symbol, [])[-count:]

    def get_positions(self, symbol: Optional[str] = None) -> List[Position]:
        if symbol is None:
            return list(self._positions)
        return [p for p in self._positions if p.symbol == symbol]

    def place_order(self, order: Order) -> Order:
        price = order.price or self._last_price(order.symbol)
        order.id = str(next(self._ids))
        self._positions.append(Position(
            symbol=order.symbol,
            side=order.side,
            volume=order.volume,
            entry_price=price,
            open_time=datetime.now(timezone.utc),
            stop_loss=order.stop_loss,
            take_profit=order.take_profit,
            id=order.id,
        ))
        return order

    def close_position(self, position: Position) -> None:
        price = self._last_price(position.symbol)
        self.balance += position.unrealized_pnl(price, self.contract_size)
        self._positions = [p for p in self._positions if p.id != position.id]
