"""Broker abstraction.

Every execution venue — the backtester, MT5, NinjaTrader — implements this
interface. The live engine and strategies only ever talk to a ``Broker``, so
switching venues is a one-line config change.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import List, Optional

from .models import Account, Bar, Order, Position


class Broker(ABC):
    """Minimal interface the engine needs to run a strategy live or in sim."""

    @abstractmethod
    def connect(self) -> None:
        """Establish a session. Raise on failure."""

    @abstractmethod
    def disconnect(self) -> None:
        """Tear down the session cleanly."""

    @abstractmethod
    def get_account(self) -> Account:
        """Current balance/equity snapshot."""

    @abstractmethod
    def get_bars(self, symbol: str, timeframe: str, count: int) -> List[Bar]:
        """Most recent ``count`` closed bars, oldest first."""

    @abstractmethod
    def get_positions(self, symbol: Optional[str] = None) -> List[Position]:
        """Open positions, optionally filtered by symbol."""

    @abstractmethod
    def place_order(self, order: Order) -> Order:
        """Submit an order. Returns the order with ``id`` populated."""

    @abstractmethod
    def close_position(self, position: Position) -> None:
        """Flatten an open position."""

    # Optional context-manager sugar so callers can ``with broker:``.
    def __enter__(self) -> "Broker":
        self.connect()
        return self

    def __exit__(self, *exc) -> None:
        self.disconnect()
