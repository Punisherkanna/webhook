"""YAML config loading and mapping to typed dataclasses.

A single ``config.yaml`` describes the broker, symbol, strategy, and risk so the
CLI can run either a backtest or a live session from one file.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict

import yaml

from .core.engine import EngineConfig
from .core.risk import RiskConfig


@dataclass
class AppConfig:
    broker: str = "paper"                 # paper | mt5 | ninjatrader
    symbol: str = "EURUSD"
    timeframe: str = "M15"
    strategy: str = "ma_crossover"
    strategy_params: Dict[str, Any] = field(default_factory=dict)
    risk: RiskConfig = field(default_factory=RiskConfig)
    engine: EngineConfig = field(default_factory=EngineConfig)
    broker_options: Dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "AppConfig":
        data = dict(data or {})
        risk = RiskConfig(**(data.get("risk") or {}))

        symbol = data.get("symbol", "EURUSD")
        timeframe = data.get("timeframe", "M15")
        engine_raw = dict(data.get("engine") or {})
        engine_raw.setdefault("symbol", symbol)
        engine_raw.setdefault("timeframe", timeframe)
        engine = EngineConfig(**engine_raw)

        return cls(
            broker=data.get("broker", "paper"),
            symbol=symbol,
            timeframe=timeframe,
            strategy=data.get("strategy", "ma_crossover"),
            strategy_params=dict(data.get("strategy_params") or {}),
            risk=risk,
            engine=engine,
            broker_options=dict(data.get("broker_options") or {}),
        )

    @classmethod
    def load(cls, path: str) -> "AppConfig":
        with open(path) as fh:
            return cls.from_dict(yaml.safe_load(fh) or {})
