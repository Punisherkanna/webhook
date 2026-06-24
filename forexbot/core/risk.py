"""Risk management and position sizing.

FX position sizing keys off pips and account currency. A *pip* is 0.0001 for
most pairs and 0.01 for JPY pairs. ``pip_value_per_lot`` is the cash value of a
one-pip move for one standard lot in the account currency.
"""
from __future__ import annotations

from dataclasses import dataclass


def pip_size(symbol: str) -> float:
    """Pip size for a symbol. JPY-quoted pairs use 0.01, others 0.0001."""
    return 0.01 if symbol.upper().endswith("JPY") else 0.0001


@dataclass
class RiskConfig:
    """Risk parameters, typically loaded from config."""

    risk_per_trade: float = 0.01      # fraction of equity risked per trade
    max_lots: float = 10.0            # hard cap on position size
    min_lots: float = 0.01            # broker minimum
    lot_step: float = 0.01            # volume granularity
    contract_size: float = 100_000.0  # units per standard lot
    max_open_positions: int = 1       # concurrency limit

    def __post_init__(self) -> None:
        if not 0 < self.risk_per_trade <= 1:
            raise ValueError("risk_per_trade must be in (0, 1]")
        if self.min_lots <= 0 or self.lot_step <= 0:
            raise ValueError("min_lots and lot_step must be positive")


class RiskManager:
    """Turns a stop distance into a broker-legal lot size."""

    def __init__(self, config: RiskConfig) -> None:
        self.config = config

    def size_for_stop(self, equity: float, symbol: str, entry: float,
                      stop: float) -> float:
        """Lots to risk ``risk_per_trade`` of ``equity`` given the stop distance.

        Returns 0.0 if the stop is invalid (zero distance) so the caller can
        skip the trade rather than blow up on a divide-by-zero.
        """
        c = self.config
        pip = pip_size(symbol)
        stop_pips = abs(entry - stop) / pip
        if stop_pips <= 0:
            return 0.0

        # Value of a one-pip move per 1.0 lot, in the quote currency.
        pip_value_per_lot = pip * c.contract_size
        risk_cash = equity * c.risk_per_trade
        raw_lots = risk_cash / (stop_pips * pip_value_per_lot)
        return self.round_lots(raw_lots)

    def round_lots(self, lots: float) -> float:
        """Snap to ``lot_step`` and clamp to [min_lots, max_lots]."""
        c = self.config
        if lots < c.min_lots:
            return 0.0  # too small to place safely
        stepped = round(lots / c.lot_step) * c.lot_step
        stepped = max(c.min_lots, min(stepped, c.max_lots))
        # Avoid binary float dust like 0.30000000000000004.
        return round(stepped, 8)
