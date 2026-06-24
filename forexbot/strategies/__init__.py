"""Strategy registry.

Maps config-friendly names to strategy classes so the CLI/config can select a
strategy by string. None of these are grid, hedging, HFT, or martingale models —
they take a single position at a time with a fixed protective stop.
"""
from __future__ import annotations

from typing import Dict, Type

from ..core.strategy import Strategy
from .ma_crossover import MACrossover
from .rsi_reversion import RSIReversion

REGISTRY: Dict[str, Type[Strategy]] = {
    "ma_crossover": MACrossover,
    "rsi_reversion": RSIReversion,
}


def get_strategy(name: str) -> Type[Strategy]:
    try:
        return REGISTRY[name]
    except KeyError:
        raise ValueError(
            f"unknown strategy '{name}'. Available: {', '.join(sorted(REGISTRY))}"
        )


__all__ = ["MACrossover", "RSIReversion", "REGISTRY", "get_strategy"]
