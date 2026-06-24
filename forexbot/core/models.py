"""Core data models shared across the backtester and live brokers.

Everything here is plain ``dataclass``/``enum`` so the core has zero third-party
dependencies and runs anywhere. Broker adapters (MT5, NinjaTrader) translate
these into their own native types.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Optional


class Side(Enum):
    """Direction of an order or position."""

    BUY = "buy"
    SELL = "sell"

    @property
    def sign(self) -> int:
        """+1 for BUY, -1 for SELL. Handy for PnL math."""
        return 1 if self is Side.BUY else -1

    def opposite(self) -> "Side":
        return Side.SELL if self is Side.BUY else Side.BUY


class OrderType(Enum):
    MARKET = "market"
    LIMIT = "limit"
    STOP = "stop"


class SignalType(Enum):
    """What a strategy wants to happen on a given bar."""

    NONE = "none"
    ENTER_LONG = "enter_long"
    ENTER_SHORT = "enter_short"
    EXIT = "exit"


@dataclass(frozen=True)
class Bar:
    """A single OHLCV candle for one symbol/timeframe."""

    timestamp: datetime
    open: float
    high: float
    low: float
    close: float
    volume: float = 0.0

    @property
    def range(self) -> float:
        return self.high - self.low


@dataclass(frozen=True)
class Tick:
    """A bid/ask quote at a point in time."""

    timestamp: datetime
    bid: float
    ask: float

    @property
    def mid(self) -> float:
        return (self.bid + self.ask) / 2.0

    @property
    def spread(self) -> float:
        return self.ask - self.bid


@dataclass(frozen=True)
class Signal:
    """A strategy's decision for a bar, optionally with risk levels."""

    type: SignalType
    stop_loss: Optional[float] = None
    take_profit: Optional[float] = None
    reason: str = ""

    @classmethod
    def none(cls) -> "Signal":
        return cls(SignalType.NONE)


@dataclass
class Order:
    """An instruction to the broker. ``id`` is filled in once accepted."""

    symbol: str
    side: Side
    volume: float
    type: OrderType = OrderType.MARKET
    price: Optional[float] = None
    stop_loss: Optional[float] = None
    take_profit: Optional[float] = None
    comment: str = ""
    id: Optional[str] = None


@dataclass
class Position:
    """An open position tracked by the engine/broker."""

    symbol: str
    side: Side
    volume: float
    entry_price: float
    open_time: datetime
    stop_loss: Optional[float] = None
    take_profit: Optional[float] = None
    id: Optional[str] = None

    def unrealized_pnl(self, price: float, contract_size: float = 100_000.0) -> float:
        """PnL in quote currency for the current ``price``.

        ``contract_size`` is the units per 1.0 lot (100k for standard FX lots).
        """
        return (price - self.entry_price) * self.side.sign * self.volume * contract_size


@dataclass
class Trade:
    """A closed round-trip, recorded by the backtester for reporting."""

    symbol: str
    side: Side
    volume: float
    entry_time: datetime
    entry_price: float
    exit_time: datetime
    exit_price: float
    pnl: float
    pnl_pips: float
    reason: str = ""


@dataclass
class Account:
    """Snapshot of account state."""

    balance: float
    equity: float
    currency: str = "USD"
    margin: float = 0.0
    positions: list = field(default_factory=list)
