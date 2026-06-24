"""NinjaTrader 8 broker adapter (file-based ATI bridge).

NinjaTrader is a C#/.NET platform with no official Python SDK. Its supported
external-control mechanism is the **Automated Trading Interface (ATI)**, which
this adapter drives through *Order Instruction Files* (OIF) — plain-text
commands dropped into::

    <Documents>/NinjaTrader 8/incoming/

Enable it in NinjaTrader: *Tools -> Options -> Automated trading interface ->
"AT Interface"* (check "Automated Trading Interface").

What this adapter does and doesn't do (be honest about the boundaries):
  * ``place_order`` / ``close_position`` -> writes OIF commands. Robust.
  * ``get_positions`` / ``get_account`` -> reads state files that a companion
    NinjaScript (or the ATI) writes back. If those files are absent the methods
    return empty/placeholder data rather than crashing.
  * ``get_bars`` -> NinjaTrader's ATI is order-centric and does not stream OHLCV
    over the file bridge. Point ``data_dir`` at a CSV that a NinjaScript
    indicator exports, or run the strategy's data feed from MT5/CSV and use this
    adapter purely for execution.

The OIF command grammar implemented here (NinjaTrader 8 ATI reference)::

    PLACE;<ACCOUNT>;<INSTRUMENT>;<ACTION>;<QTY>;<ORDER TYPE>;[LIMIT];[STOP];\
        [TIF];[OCO];[ORDER ID];[STRATEGY];[STRATEGY ID]
    CLOSEPOSITION;<ACCOUNT>;<INSTRUMENT>
"""
from __future__ import annotations

import os
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Optional

from ..core.broker import Broker
from ..core.models import Account, Bar, Order, OrderType, Position, Side
from .csv_feed import read_bar_csv


def _default_incoming() -> Path:
    return Path.home() / "Documents" / "NinjaTrader 8" / "incoming"


class NinjaTraderBroker(Broker):
    def __init__(self, account: str = "Sim101",
                 incoming_dir: Optional[str] = None,
                 state_dir: Optional[str] = None,
                 data_dir: Optional[str] = None) -> None:
        self.account = account
        self.incoming_dir = Path(incoming_dir) if incoming_dir else _default_incoming()
        # State/data files written back by a companion NinjaScript (optional).
        self.state_dir = Path(state_dir) if state_dir else self.incoming_dir.parent
        self.data_dir = Path(data_dir) if data_dir else None
        self._seq = 0

    # --- lifecycle ----------------------------------------------------------
    def connect(self) -> None:
        self.incoming_dir.mkdir(parents=True, exist_ok=True)
        if not self.incoming_dir.is_dir():
            raise RuntimeError(f"incoming dir not writable: {self.incoming_dir}")

    def disconnect(self) -> None:
        pass  # nothing persistent to tear down for a file bridge

    # --- command writer -----------------------------------------------------
    def _write_command(self, command: str) -> str:
        """Drop a single OIF command into a uniquely-named file."""
        self._seq += 1
        name = f"oif_{int(time.time() * 1000)}_{self._seq}.txt"
        path = self.incoming_dir / name
        tmp = path.with_suffix(".tmp")
        tmp.write_text(command + "\n")
        os.replace(tmp, path)  # atomic so NT never reads a half-written file
        return str(path)

    @staticmethod
    def _action(side: Side) -> str:
        return "BUY" if side is Side.BUY else "SELL"

    @staticmethod
    def _order_type(t: OrderType) -> str:
        return {OrderType.MARKET: "MARKET", OrderType.LIMIT: "LIMIT",
                OrderType.STOP: "STOP"}[t]

    # --- Broker interface ---------------------------------------------------
    def place_order(self, order: Order) -> Order:
        self._seq += 1
        order_id = order.id or f"forexbot-{int(time.time())}-{self._seq}"
        limit = f"{order.price:.5f}" if order.type is OrderType.LIMIT and order.price else ""
        stop = f"{order.price:.5f}" if order.type is OrderType.STOP and order.price else ""
        command = ";".join([
            "PLACE", self.account, order.symbol, self._action(order.side),
            str(int(order.volume)) if order.volume.is_integer() else str(order.volume),
            self._order_type(order.type), limit, stop, "GTC", "", order_id, "", "",
        ])
        self._write_command(command)
        order.id = order_id

        # Attach protective stop/target as separate OCO orders if requested.
        if order.stop_loss is not None or order.take_profit is not None:
            self._write_protective_orders(order)
        return order

    def _write_protective_orders(self, order: Order) -> None:
        oco = f"oco-{order.id}"
        exit_side = order.side.opposite()
        if order.stop_loss is not None:
            self._write_command(";".join([
                "PLACE", self.account, order.symbol, self._action(exit_side),
                str(int(order.volume)) if float(order.volume).is_integer() else str(order.volume),
                "STOP", "", f"{order.stop_loss:.5f}", "GTC", oco,
                f"{order.id}-sl", "", "",
            ]))
        if order.take_profit is not None:
            self._write_command(";".join([
                "PLACE", self.account, order.symbol, self._action(exit_side),
                str(int(order.volume)) if float(order.volume).is_integer() else str(order.volume),
                "LIMIT", f"{order.take_profit:.5f}", "", "GTC", oco,
                f"{order.id}-tp", "", "",
            ]))

    def close_position(self, position: Position) -> None:
        self._write_command(
            ";".join(["CLOSEPOSITION", self.account, position.symbol])
        )

    def get_positions(self, symbol: Optional[str] = None) -> List[Position]:
        """Read positions from ``<state_dir>/positions.csv`` if a companion
        NinjaScript exports it. Returns ``[]`` when unavailable."""
        path = self.state_dir / "positions.csv"
        if not path.exists():
            return []
        positions: List[Position] = []
        for line in path.read_text().splitlines():
            line = line.strip()
            if not line or line.lower().startswith("symbol"):
                continue
            # Expected: symbol,side,qty,avg_price
            parts = [p.strip() for p in line.split(",")]
            if len(parts) < 4:
                continue
            sym, side, qty, avg = parts[:4]
            if symbol and sym != symbol:
                continue
            positions.append(Position(
                symbol=sym,
                side=Side.BUY if side.upper().startswith("B") else Side.SELL,
                volume=float(qty),
                entry_price=float(avg),
                open_time=datetime.now(timezone.utc),
            ))
        return positions

    def get_account(self) -> Account:
        """Read ``<state_dir>/account.csv`` (``balance,equity``) if present."""
        path = self.state_dir / "account.csv"
        if path.exists():
            for line in path.read_text().splitlines():
                line = line.strip()
                if not line or line.lower().startswith("balance"):
                    continue
                parts = [p.strip() for p in line.split(",")]
                if len(parts) >= 2:
                    return Account(balance=float(parts[0]), equity=float(parts[1]))
        return Account(balance=0.0, equity=0.0)

    def get_bars(self, symbol: str, timeframe: str, count: int) -> List[Bar]:
        """Read bars from a NinjaScript-exported CSV in ``data_dir``.

        File is expected at ``<data_dir>/<symbol>_<timeframe>.csv``. Raises a
        clear error if no ``data_dir`` was configured, since the ATI bridge
        itself does not provide market data.
        """
        if self.data_dir is None:
            raise RuntimeError(
                "NinjaTrader ATI does not stream bars over the file bridge. "
                "Set data_dir to a NinjaScript CSV export, or feed bars from "
                "MT5/CSV and use this adapter for execution only."
            )
        path = self.data_dir / f"{symbol}_{timeframe}.csv"
        return read_bar_csv(path)[-count:]
