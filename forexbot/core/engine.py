"""Live trading engine.

Polls a :class:`Broker` for fresh bars, runs them through a :class:`Strategy`,
sizes trades with the :class:`RiskManager`, and submits orders. It is broker- and
strategy-agnostic: the same loop drives the paper broker, MT5, or NinjaTrader.

The loop intentionally acts on *closed* bars only (no trading on a forming bar),
which keeps live behaviour consistent with the backtester.
"""
from __future__ import annotations

import logging
import time
from dataclasses import dataclass
from typing import Optional

from .broker import Broker
from .models import Order, OrderType, Side, SignalType
from .risk import RiskConfig, RiskManager
from .strategy import Strategy

log = logging.getLogger("forexbot.engine")


@dataclass
class EngineConfig:
    symbol: str = "EURUSD"
    timeframe: str = "M15"
    history: int = 200          # bars to pull each poll
    poll_seconds: float = 5.0
    dry_run: bool = True        # log intended orders without sending


class TradingEngine:
    def __init__(self, broker: Broker, strategy: Strategy,
                 risk: RiskConfig, config: EngineConfig) -> None:
        self.broker = broker
        self.strategy = strategy
        self.risk = RiskManager(risk)
        self.config = config
        self._last_bar_time = None
        self._running = False

    def run_forever(self) -> None:
        """Blocking loop. Stops on Ctrl-C or :meth:`stop`."""
        self._running = True
        self.broker.connect()
        log.info("engine started: %s %s (dry_run=%s)",
                 self.config.symbol, self.config.timeframe, self.config.dry_run)
        try:
            while self._running:
                try:
                    self.poll_once()
                except Exception:  # keep the loop alive on transient errors
                    log.exception("poll failed; continuing")
                time.sleep(self.config.poll_seconds)
        except KeyboardInterrupt:
            log.info("interrupted; shutting down")
        finally:
            self.broker.disconnect()

    def stop(self) -> None:
        self._running = False

    def poll_once(self) -> Optional[Order]:
        """Run a single decision cycle. Returns an Order if one was placed."""
        cfg = self.config
        bars = self.broker.get_bars(cfg.symbol, cfg.timeframe, cfg.history)
        if not bars:
            return None

        latest = bars[-1]
        if self._last_bar_time == latest.timestamp:
            return None  # no new closed bar yet
        self._last_bar_time = latest.timestamp

        # Replay any history the strategy hasn't seen so indicators are warm.
        # On the first poll we feed everything; thereafter just the new bar.
        if not self.strategy.bars:
            signal = None
            for bar in bars:
                signal = self.strategy.update(bar)
        else:
            signal = self.strategy.update(latest)

        if signal is None or signal.type is SignalType.NONE:
            return None

        open_positions = self.broker.get_positions(cfg.symbol)

        if signal.type is SignalType.EXIT:
            for pos in open_positions:
                self._maybe_close(pos)
            return None

        # Entry signals: respect the concurrency cap.
        if len(open_positions) >= self.risk.config.max_open_positions:
            log.info("entry skipped: max_open_positions reached")
            return None

        return self._enter(signal, latest.close)

    # --- helpers ------------------------------------------------------------
    def _enter(self, signal, price: float) -> Optional[Order]:
        side = Side.BUY if signal.type is SignalType.ENTER_LONG else Side.SELL
        if signal.stop_loss is None:
            log.warning("entry skipped: signal has no stop loss")
            return None

        equity = self.broker.get_account().equity
        lots = self.risk.size_for_stop(equity, self.config.symbol, price,
                                       signal.stop_loss)
        if lots <= 0:
            log.warning("entry skipped: computed size is zero")
            return None

        order = Order(
            symbol=self.config.symbol,
            side=side,
            volume=lots,
            type=OrderType.MARKET,
            stop_loss=signal.stop_loss,
            take_profit=signal.take_profit,
            comment=f"{self.strategy.name}: {signal.reason}",
        )
        if self.config.dry_run:
            log.info("[dry_run] would place %s %.2f lots %s sl=%.5f tp=%s",
                     side.value, lots, self.config.symbol, signal.stop_loss,
                     signal.take_profit)
            return order
        placed = self.broker.place_order(order)
        log.info("placed order %s: %s %.2f lots", placed.id, side.value, lots)
        return placed

    def _maybe_close(self, position) -> None:
        if self.config.dry_run:
            log.info("[dry_run] would close %s %s", position.side.value,
                     position.symbol)
            return
        self.broker.close_position(position)
        log.info("closed position %s", position.id)
